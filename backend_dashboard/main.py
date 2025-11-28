import os
import logging
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

from fastapi import FastAPI, HTTPException, UploadFile, File 
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Imports de tus herramientas
from agents.main_agent import get_agent_response
from tools.dashboard import obtener_datos_raw
from tools.docs import procesar_pdf_subido
from tools.audio import procesar_audio_gemini
# Importamos las funciones de base de datos
from tools.database import guardar_acta, obtener_historial_actas, borrar_acta

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("backend_main")

app = FastAPI()

# --- SEGURIDAD CORS ---
origenes_permitidos = [
    "http://localhost:5173", # Vite default
    "http://localhost:3000", # React default
    "https://tudominio.ar",  # Tu dominio real
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origenes_permitidos, 
    allow_origin_regex=r"https://.*\.vercel\.app", 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)

@app.get("/")
def read_root():
    return {"status": "online", "system": "MinCYT Dashboard & AI"}

# --- ENDPOINT DE CHAT ---
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

# --- ENDPOINT DE DATOS (DASHBOARD) ---
@app.get("/api/data")
def get_dashboard_data():
    try:
        datos = obtener_datos_raw()
        return datos
    except Exception as e:
        logger.error(f"Error al obtener datos: {e}")
        raise HTTPException(status_code=500, detail="Error de base de datos")

# --- ENDPOINT DE SUBIDA PDF ---
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

# --- ENDPOINT DE VOZ (GRABACIÓN + SUPABASE) ---
@app.post("/api/voice")
async def voice_endpoint(file: UploadFile = File(...)):
    if not file.content_type.startswith('audio/'):
         raise HTTPException(status_code=400, detail="El archivo debe ser audio")
    
    try:
        # 1. Transcribir con Gemini
        texto_transcrito = procesar_audio_gemini(file)
        
        # 2. Guardar en Supabase automáticamente
        if texto_transcrito:
            print(f"💾 Intentando guardar acta...")
            guardar_acta(transcripcion=texto_transcrito, resumen="Pendiente de análisis")
            
        return {"text": texto_transcrito}
        
    except Exception as e:
        logger.error(f"Error procesando audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# --- ENDPOINTS DE HISTORIAL (MEETINGS) ---
@app.get("/api/meetings")
def get_meetings():
    """Devuelve la lista de reuniones guardadas"""
    try:
        history = obtener_historial_actas()
        return history
    except Exception as e:
        logger.error(f"Error fetching meetings: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener el historial")

@app.delete("/api/meetings/{meeting_id}")
def delete_meeting(meeting_id: int):
    """Borra una reunión específica"""
    try:
        exito = borrar_acta(meeting_id)
        if exito:
            return {"status": "ok", "message": f"Reunión {meeting_id} eliminada"}
        else:
            raise HTTPException(status_code=404, detail="Reunión no encontrada o no se pudo borrar")
    except Exception as e:
        logger.error(f"Error deleting meeting: {e}")
        raise HTTPException(status_code=500, detail="Error interno al borrar")
