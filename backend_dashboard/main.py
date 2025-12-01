import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional

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

# --- ENDPOINTS GENERALES ---

@app.get("/")
def read_root():
    return {"status": "online", "system": "MinCYT Dashboard & AI v2.0"}

@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    try:
        # Pasamos el mensaje Y el historial al agente
        respuesta = get_agent_response(request.message, request.history)
        return {"response": respuesta}
    except Exception as e:
        logger.error(f"❌ Error en chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del asistente")

# --- ENDPOINTS DE DATOS (AGENDA) ---

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
            raise HTTPException(status_code=500, detail=mensaje)
    except Exception as e:
        logger.error(f"Error upload: {e}")
        raise HTTPException(500, detail="Error procesando archivo")

@app.post("/upload-audio/") 
def upload_audio_endpoint(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.content_type.startswith('audio/'):
         raise HTTPException(status_code=400, detail="El archivo debe ser de audio.")
    try:
        # 1. Transcribir (El usuario espera esto)
        texto = procesar_audio_gemini(file)
        
        # 2. Guardar en BD en segundo plano (El usuario NO espera esto)
        # Nota: Asegúrate de que 'procesar_audio_gemini' devuelva el texto limpio
        # y que 'guardar_acta' maneje la inserción.
        if texto:
            background_tasks.add_task(guardar_acta, transcripcion=texto)
        
        return {"mensaje": "Éxito", "transcripcion": texto}
    except Exception as e:
        logger.error(f"Error audio: {e}")
        raise HTTPException(500, detail=str(e))

# --- ENDPOINTS DE ACTAS ---

@app.get("/actas")
def get_actas():
    return obtener_historial_actas()

@app.delete("/actas/{id_acta}")
def delete_acta_endpoint(id_acta: int):
    if borrar_acta(id_acta): 
        return {"status": "ok"}
    raise HTTPException(404, detail="No encontrado")