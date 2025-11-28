import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File 
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Imports de tus herramientas
from agents.main_agent import get_agent_response
from tools.dashboard import obtener_datos_raw
from tools.docs import procesar_pdf_subido
from tools.audio import procesar_audio_gemini
from tools.database import guardar_acta, obtener_historial_actas, borrar_acta

# Cargar variables de entorno
load_dotenv()

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("backend_main")

app = FastAPI()

# --- SEGURIDAD CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite todo por ahora para evitar errores de conexión
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)

@app.get("/")
def read_root():
    return {"status": "online", "system": "MinCYT Dashboard & AI"}

# --- 1. ENDPOINT DE CHAT (Mantenido) ---
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        respuesta = get_agent_response(request.message)
        return {"response": respuesta}
    except ValueError as ve:
        logger.warning(f"Error de validación en chat: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"❌ Error crítico en chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error procesando la solicitud del agente")

# --- 2. ENDPOINT DE DATOS DASHBOARD (Mantenido) ---
@app.get("/api/data")
def get_dashboard_data():
    try:
        datos = obtener_datos_raw()
        return datos
    except Exception as e:
        logger.error(f"Error al obtener datos: {e}")
        raise HTTPException(status_code=500, detail="Error de base de datos")

# --- 3. ENDPOINT DE SUBIDA PDF (Mantenido) ---
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF")
    
    try:
        exito, mensaje = procesar_pdf_subido(file)
        if exito:
            return {"status": "ok", "message": mensaje}
        else:
            raise HTTPException(status_code=500, detail=mensaje)
    except Exception as e:
        logger.error(f"Error subiendo archivo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error procesando el archivo")

# --- 4. ENDPOINT DE VOZ / GRABACIÓN (ACTUALIZADO) ---
# Este nombre de ruta coincide con lo que pusimos en MeetingRecorder.tsx
@app.post("/upload-audio/") 
async def upload_audio_endpoint(file: UploadFile = File(...)):
    logger.info(f"Recibiendo audio: {file.filename} type: {file.content_type}")

    # Validación simple de tipo
    if not file.content_type.startswith('audio/'):
         raise HTTPException(status_code=400, detail="El archivo debe ser audio")
    
    try:
        # 1. Transcribir
        texto_transcrito = procesar_audio_gemini(file)
        
        # 2. Guardar en base de datos
        # (Aquí se guarda con resumen 'Pendiente' o null por ahora)
        acta_guardada = None
        if texto_transcrito:
            logger.info(f"💾 Guardando acta en Supabase...")
            # Nota: database.py devuelve una lista "data", tomamos el primer elemento si existe
            resultado_db = guardar_acta(transcripcion=texto_transcrito, resumen=None)
            if resultado_db and len(resultado_db) > 0:
                acta_guardada = resultado_db[0]

        return {
            "mensaje": "Procesamiento exitoso",
            "transcripcion": texto_transcrito,
            "acta": acta_guardada
        }
        
    except Exception as e:
        logger.error(f"Error procesando audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# --- 5. ENDPOINTS DE HISTORIAL / ACTAS (ACTUALIZADO) ---
# Coincide con MeetingHistory.tsx: fetch(`${API_URL}/actas`)

@app.get("/actas")
def get_actas():
    try:
        history = obtener_historial_actas()
        return history
    except Exception as e:
        logger.error(f"Error fetching actas: {e}")
        # Retornamos lista vacía en vez de error 500 para que el front no rompa
        return []

@app.delete("/actas/{id_acta}")
def delete_acta_endpoint(id_acta: int):
    try:
        exito = borrar_acta(id_acta)
        if exito:
            return {"status": "ok", "message": f"Acta {id_acta} eliminada"}
        else:
            raise HTTPException(status_code=404, detail="Acta no encontrada o no se pudo borrar")
    except Exception as e:
        logger.error(f"Error deleting acta: {e}")
        raise HTTPException(status_code=500, detail="Error interno al borrar")