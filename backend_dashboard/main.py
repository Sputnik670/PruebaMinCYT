import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse  # <--- NUEVO: Para Streaming
from pydantic import BaseModel, Field
from typing import List, Optional, Generator


from agents.main_agent import get_agent_response
from tools.dashboard import (
    get_data_cliente_formatted,
    get_data_ministerio_formatted,
    obtener_datos_raw,
    SHEET_CLIENTE_ID
)
from tools.docs import procesar_archivo_subido 
from tools.audio import procesar_audio_gemini
from tools.database import guardar_acta, obtener_historial_actas, borrar_acta
from monitoring import session_manager

load_dotenv()

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("backend_main")

app = FastAPI(title="MinCYT AI Dashboard", version="2.0.0")

# Configuración CORS
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # CORRECCIÓN AUDITORÍA: Uso de 'r' para raw string en regex
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
    session_id: Optional[str] = None  # ← NUEVO
    user_id: str = "usuario_anonimo"  # ← NUEVO

# --- ENDPOINTS GENERALES ---

@app.get("/")
def read_root():
    return {"status": "online", "system": "MinCYT Dashboard & AI v2.0"}

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint optimizado con Sistema de Sesiones Persistentes
    """
    async def generate_response_stream():
        try:
            # 🆕 GESTIÓN DE SESIONES
            session_id = request.session_id
            if not session_id:
                # Crear nueva sesión automáticamente
                titulo_sesion = f"Chat: {request.message[:30]}..."
                session_id = session_manager.crear_nueva_sesion(request.user_id, titulo_sesion)
                # Informar al frontend del nuevo session_id
                yield f"data: SESSION_ID:{session_id}\n\n"
            
            # 🆕 RECUPERAR HISTORIAL DE SESIÓN
            historial_previo = []
            if not request.history:
                # Si no hay historial en la request, obtenerlo de la BD
                historial_bd = session_manager.obtener_historial_sesion(session_id, limite=10)
                
                # Convertir formato BD → formato Message
                for msg in historial_bd:
                    if msg.get('mensaje_usuario'):
                        historial_previo.append(Message(
                            id=f"user_{msg['id']}",
                            text=msg['mensaje_usuario'],
                            sender="user",
                            timestamp=msg['timestamp']
                        ))
                    if msg.get('respuesta_bot'):
                        historial_previo.append(Message(
                            id=f"bot_{msg['id']}",
                            text=msg['respuesta_bot'],
                            sender="assistant",
                            timestamp=msg['timestamp']
                        ))
            else:
                historial_previo = request.history

            # Llamar al agente con historial completo
            respuesta = get_agent_response(request.message, historial_previo)
            
            # Manejar streaming y capturar respuesta completa
            respuesta_completa = ""
            
            if hasattr(respuesta, '__iter__') and not isinstance(respuesta, str):
                # Streaming response
                for chunk in respuesta:
                    respuesta_completa += chunk
                    yield f"data: {chunk}\n\n"
            else:
                # Respuesta completa
                respuesta_completa = respuesta
                yield f"data: {respuesta}\n\n"
            
            # 🆕 GUARDAR LA CONVERSACIÓN
            session_manager.guardar_mensaje(
                sesion_id=session_id,
                mensaje_usuario=request.message,
                respuesta_bot=respuesta_completa,
                herramientas_usadas=[]  # TODO: capturar desde el agente
            )

        except Exception as e:
            logger.error(f"❌ Error crítico en chat_endpoint: {str(e)}", exc_info=True)
            yield f"data: Error del sistema: {str(e)}\n\n"

    return StreamingResponse(generate_response_stream(), media_type="text/plain")

# --- ENDPOINTS DE DATOS (AGENDA) ---

@app.get("/api/agenda/ministerio")
def get_agenda_ministerio_endpoint():
    """Devuelve la tabla oficial limpia"""
    try:
        data = get_data_ministerio_formatted()
        return data
    except Exception as e:
        logger.error(f"Error agenda ministerio: {e}")
        return []

@app.get("/api/agenda/cliente")
def get_agenda_cliente_endpoint():
    """Devuelve la tabla de gestión limpia"""
    try:
        data = get_data_cliente_formatted()
        return data
    except Exception as e:
        logger.error(f"Error agenda cliente: {e}")
        return []

@app.get("/api/data")
def get_dashboard_data():
    """Endpoint fallback (devuelve cliente por defecto)"""
    return get_data_cliente_formatted()

# --- ENDPOINTS DE ARCHIVOS Y AUDIO ---

@app.post("/api/upload")
def upload_file_endpoint(file: UploadFile = File(...)):
    # Extensiones permitidas: PDF, Excel, CSV, Word, TXT
    allowed_extensions = ('.pdf', '.xlsx', '.xls', '.csv', '.docx', '.txt')
    
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail="Formato no permitido. Solo PDF, Excel, Word, CSV o TXT.")
    
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
        # 1. Transcribir (El usuario espera esto en tiempo real)
        texto = procesar_audio_gemini(file)
        
        # 2. Guardar en BD en segundo plano (Background Task para no bloquear)
        if texto:
            background_tasks.add_task(guardar_acta, transcripcion=texto)
        
        return {"mensaje": "Éxito", "transcripcion": texto}
    except Exception as e:
        logger.error(f"Error procesando audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
    # --- ENDPOINTS DE SESIONES ---

@app.get("/api/sesiones/{user_id}")
def get_sesiones_usuario(user_id: str):
    """Obtener historial de sesiones de un usuario"""
    try:
        sesiones = session_manager.listar_sesiones_usuario(user_id, limite=20)
        return {"sesiones": sesiones}
    except Exception as e:
        logger.error(f"Error obteniendo sesiones: {e}")
        return {"sesiones": []}

@app.get("/api/sesiones/{sesion_id}/historial")
def get_historial_sesion(sesion_id: str):
    """Obtener historial detallado de una sesión"""
    try:
        historial = session_manager.obtener_historial_sesion(sesion_id, limite=50)
        return {"historial": historial}
    except Exception as e:
        logger.error(f"Error obteniendo historial: {e}")
        return {"historial": []}

# --- ENDPOINTS DE ACTAS ---

@app.get("/actas")
def get_actas():
    try:
        return obtener_historial_actas()
    except Exception as e:
        logger.error(f"Error obteniendo actas: {e}")
        return []

@app.delete("/actas/{id_acta}")
def delete_acta_endpoint(id_acta: int):
    try:
        if borrar_acta(id_acta): 
            return {"status": "ok"}
        raise HTTPException(status_code=404, detail="Acta no encontrada")
    except Exception as e:
        logger.error(f"Error borrando acta {id_acta}: {e}")
        raise HTTPException(status_code=500, detail="Error interno al borrar")