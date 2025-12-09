import os
import logging
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional

# --- IMPORTACIONES DEL SISTEMA ---
from agents.main_agent import get_agent_response
from tools.docs import procesar_archivo_subido 
from tools.audio import procesar_audio_gemini
from tools.database import guardar_acta, obtener_historial_actas, borrar_acta
from monitoring import session_manager

# Importamos el nuevo servicio de sincronización (Asegúrate de crear este archivo después)
from services.sync_sheets import sincronizar_google_a_supabase

load_dotenv()

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("backend_main")

# --- LIFESPAN (Ciclo de Vida: Tareas de fondo automáticas) ---
async def ciclo_sincronizacion():
    """Ejecuta la sincronización con Google Sheets cada 10 minutos"""
    while True:
        try:
            logger.info("🔄 Ejecutando auto-sync Google Sheets...")
            # Ejecutamos en un hilo aparte para no bloquear el servidor
            await asyncio.to_thread(sincronizar_google_a_supabase)
        except Exception as e:
            logger.error(f"⚠️ Error en ciclo de sync: {e}")
        
        # Esperar 600 segundos (10 minutos)
        await asyncio.sleep(600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Al iniciar la app: lanzar el bucle
    task = asyncio.create_task(ciclo_sincronizacion())
    yield
    # Al cerrar la app: cancelar (opcional, aquí dejamos que muera con el proceso)
    task.cancel()

app = FastAPI(title="MinCYT AI Dashboard", version="2.2.0", lifespan=lifespan)

# --- CONFIGURACIÓN CORS (SEGURIDAD) ---
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://pruebamin-cy-t.vercel.app",
    "https://pruebamincyt-q4reoctt1-sputnik670s-projects.vercel.app",
    "https://www.pruebasmincyt.ar",
    "https://pruebasmincyt.ar",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,       
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=r"https://.*\.vercel\.app",
)

# --- MODELOS PYDANTIC ---

class Message(BaseModel):
    id: str
    text: str
    sender: str
    timestamp: str 

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: Optional[List[Message]] = []
    session_id: Optional[str] = None 
    user_id: str = "usuario_anonimo"

# --- ENDPOINTS GENERALES ---

@app.get("/")
def read_root():
    return {"status": "online", "system": "MinCYT Dashboard & AI v2.2 (Auto-Sync Activo)"}

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint de Chat optimizado con Streaming y Sesiones
    """
    async def generate_response_stream():
        try:
            session_id = request.session_id
            
            # Auto-creación de sesión si no existe o es temporal
            if not session_id or str(session_id).startswith("local-"):
                titulo_sesion = f"Chat: {request.message[:30]}..."
                session_id = session_manager.crear_nueva_sesion(request.user_id, titulo_sesion)
                yield f"data: SESSION_ID:{session_id}\n\n"
            
            # Recuperación de historial
            historial_previo = []
            if not request.history:
                historial_bd = session_manager.obtener_historial_sesion(session_id, limite=10)
                for msg in historial_bd:
                    if msg.get('mensaje_usuario'):
                        historial_previo.append(Message(
                            id=f"user_{msg['id']}", text=msg['mensaje_usuario'], sender="user", timestamp=msg['timestamp']
                        ))
                    if msg.get('respuesta_bot'):
                        historial_previo.append(Message(
                            id=f"bot_{msg['id']}", text=msg['respuesta_bot'], sender="assistant", timestamp=msg['timestamp']
                        ))
            else:
                historial_previo = request.history

            # Generación de respuesta (Agente)
            respuesta = get_agent_response(request.message, historial_previo)
            
            respuesta_completa = ""
            if hasattr(respuesta, '__iter__') and not isinstance(respuesta, str):
                for chunk in respuesta:
                    respuesta_completa += chunk
                    yield f"data: {chunk}\n\n"
            else:
                respuesta_completa = respuesta
                yield f"data: {respuesta}\n\n"
            
            # Guardado
            session_manager.guardar_mensaje(
                sesion_id=session_id,
                mensaje_usuario=request.message,
                respuesta_bot=respuesta_completa,
                herramientas_usadas=[] 
            )

        except Exception as e:
            logger.error(f"❌ Error crítico en chat_endpoint: {str(e)}", exc_info=True)
            yield f"data: Error del sistema: {str(e)}\n\n"

    return StreamingResponse(generate_response_stream(), media_type="text/plain")

# --- ENDPOINTS DE ARCHIVOS Y AUDIO ---

@app.post("/api/upload")
def upload_file_endpoint(file: UploadFile = File(...)):
    # Extensiones permitidas para RAG (Búsqueda documental)
    allowed_extensions = ('.pdf', '.xlsx', '.xls', '.csv', '.docx', '.txt')
    
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail="Formato no permitido.")
    
    try:
        exito, mensaje = procesar_archivo_subido(file)
        if exito:
            return {"status": "ok", "message": mensaje}
        else:
            logger.warning(f"Fallo procesamiento archivo: {mensaje}")
            raise HTTPException(status_code=500, detail=mensaje)
    except Exception as e:
        logger.error(f"Error upload exception: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno procesando archivo")

@app.post("/upload-audio/") 
def upload_audio_endpoint(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.content_type.startswith('audio/'):
         raise HTTPException(status_code=400, detail="El archivo debe ser de audio válido.")
    
    try:
        texto = procesar_audio_gemini(file)
        if texto:
            background_tasks.add_task(guardar_acta, transcripcion=texto)
        return {"mensaje": "Éxito", "transcripcion": texto}
    except Exception as e:
        logger.error(f"Error procesando audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINTS DE SESIONES Y ACTAS ---

@app.get("/api/sesiones/{user_id}")
def get_sesiones_usuario(user_id: str):
    try:
        sesiones = session_manager.listar_sesiones_usuario(user_id, limite=20)
        return {"sesiones": sesiones}
    except Exception as e:
        return {"sesiones": []}

@app.get("/api/sesiones/{sesion_id}/historial")
def get_historial_sesion(sesion_id: str):
    try:
        historial = session_manager.obtener_historial_sesion(sesion_id, limite=50)
        return {"historial": historial}
    except Exception as e:
        return {"historial": []}

@app.get("/actas")
def get_actas():
    try:
        return obtener_historial_actas()
    except Exception as e:
        return []

@app.delete("/actas/{id_acta}")
def delete_acta_endpoint(id_acta: int):
    try:
        if borrar_acta(id_acta): return {"status": "ok"}
        raise HTTPException(status_code=404, detail="Acta no encontrada")
    except Exception:
        raise HTTPException(status_code=500, detail="Error interno al borrar")