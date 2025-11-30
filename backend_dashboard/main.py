import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File 
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.main_agent import get_agent_response
from tools.dashboard import (
    get_data_cliente_formatted,      # <--- NUEVO
    get_data_ministerio_formatted,   # <--- NUEVO
    obtener_datos_raw,
    SHEET_CLIENTE_ID
)
from tools.docs import procesar_archivo_subido 
from tools.audio import procesar_audio_gemini
from tools.database import guardar_acta, obtener_historial_actas, borrar_acta

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("backend_main")

app = FastAPI(title="MinCYT AI Dashboard", version="2.0.0")

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)

@app.get("/")
def read_root():
    return {"status": "online", "system": "MinCYT Dashboard & AI v2.0"}

@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    try:
        respuesta = get_agent_response(request.message)
        return {"response": respuesta}
    except Exception as e:
        logger.error(f"❌ Error en chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del asistente")

# --- ENDPOINTS DE DATOS SEPARADOS ---

@app.get("/api/agenda/ministerio")
def get_agenda_ministerio_endpoint():
    """Devuelve la tabla oficial limpia"""
    try:
        return get_data_ministerio_formatted()
    except Exception as e:
        logger.error(f"Error agenda ministerio: {e}")
        return []

@app.get("/api/agenda/cliente")
def get_agenda_cliente_endpoint():
    """Devuelve la tabla de gestión limpia"""
    try:
        return get_data_cliente_formatted()
    except Exception as e:
        logger.error(f"Error agenda cliente: {e}")
        return []

@app.get("/api/data")
def get_dashboard_data():
    """Endpoint fallback (devuelve cliente por defecto)"""
    return get_data_cliente_formatted()

# --- RESTO DE ENDPOINTS (Upload, Audio, Actas) ---
@app.post("/api/upload")
def upload_file_endpoint(file: UploadFile = File(...)):
    allowed_extensions = ('.pdf', '.xlsx', '.xls', '.csv')
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail="Formato no permitido")
    try:
        exito, mensaje = procesar_archivo_subido(file)
        return {"status": "ok", "message": mensaje} if exito else HTTPException(500, detail=mensaje)
    except Exception as e:
        logger.error(f"Error upload: {e}")
        raise HTTPException(500, detail="Error procesando archivo")

@app.post("/upload-audio/") 
def upload_audio_endpoint(file: UploadFile = File(...)):
    if not file.content_type.startswith('audio/'):
         raise HTTPException(status_code=400, detail="Debe ser audio")
    try:
        texto = procesar_audio_gemini(file)
        if texto: guardar_acta(transcripcion=texto, resumen=None)
        return {"mensaje": "Éxito", "transcripcion": texto}
    except Exception as e:
        logger.error(f"Error audio: {e}")
        raise HTTPException(500, detail=str(e))

@app.get("/actas")
def get_actas():
    return obtener_historial_actas()

@app.delete("/actas/{id_acta}")
def delete_acta_endpoint(id_acta: int):
    if borrar_acta(id_acta): return {"status": "ok"}
    raise HTTPException(404, detail="No encontrado")