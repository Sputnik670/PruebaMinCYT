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

# --- ENDPOINTS GENERALES ---

@app.get("/")
def read_root():
    return {"status": "online", "system": "MinCYT Dashboard & AI v2.0"}

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Endpoint optimizado para Streaming.
    Permite que el frontend reciba la respuesta progresivamente.
    """
    async def generate_response_stream():
        try:
            # Llamamos al agente. 
            # NOTA: Para obtener el beneficio completo del streaming, 
            # 'get_agent_response' en main_agent.py debería actualizarse para usar 'yield'.
            # Este código es compatible con ambas versiones (string o generador).
            respuesta = get_agent_response(request.message, request.history)
            
            if hasattr(respuesta, '__iter__') and not isinstance(respuesta, str):
                # Si el agente ya soporta streaming real (es un generador)
                for chunk in respuesta:
                    yield chunk
            else:
                # Si el agente devuelve todo el texto de una vez (legacy)
                yield respuesta

        except Exception as e:
            logger.error(f"❌ Error crítico en chat_endpoint: {str(e)}", exc_info=True)
            yield f"Error del sistema: {str(e)}"

    # Retornamos un StreamingResponse con media_type text/plain para facilitar la lectura en el frontend
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