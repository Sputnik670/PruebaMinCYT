import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File 
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# --- IMPORTS ACTUALIZADOS ---
from agents.main_agent import get_agent_response
# Importamos las nuevas constantes y la función genérica
from tools.dashboard import (
    obtener_datos_sheet, 
    SHEET_MINISTERIO_ID, 
    WORKSHEET_MINISTERIO_GID,
    SHEET_CLIENTE_ID,
    WORKSHEET_CLIENTE_GID
)
from tools.docs import procesar_archivo_subido 
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

app = FastAPI(title="MinCYT AI Dashboard", version="2.0.0")

# --- SEGURIDAD CORS ---
origins = [
    "http://localhost:5173",  # Tu entorno local
    "http://127.0.0.1:5173",  
    "https://pruebamincyt.vercel.app", 
    "https://pruebamincyt.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 👈 ¡ESTO ES LA CLAVE! El asterisco permite cualquier origen.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)

@app.get("/")
def read_root():
    return {"status": "online", "system": "MinCYT Dashboard & AI v2.0"}

# --- 1. ENDPOINT DE CHAT ---
@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    try:
        respuesta = get_agent_response(request.message)
        return {"response": respuesta}
    except Exception as e:
        logger.error(f"❌ Error en chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del asistente")

# --- 2. ENDPOINTS DE AGENDA (DOBLE VÍA) ---

@app.get("/api/agenda/ministerio")
def get_agenda_ministerio():
    """Devuelve la tabla oficial del ministerio"""
    try:
        datos = obtener_datos_sheet(SHEET_MINISTERIO_ID, WORKSHEET_MINISTERIO_GID)
        return datos
    except Exception as e:
        logger.error(f"Error agenda ministerio: {e}")
        raise HTTPException(status_code=500, detail="Error leyendo agenda oficial")

@app.get("/api/agenda/cliente")
def get_agenda_cliente():
    """Devuelve la tabla privada del cliente"""
    try:
        if "PON_AQUI" in SHEET_CLIENTE_ID:
             return [{"Error": "ID de hoja no configurado en backend"}]
             
        datos = obtener_datos_sheet(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
        return datos
    except Exception as e:
        logger.error(f"Error agenda cliente: {e}")
        raise HTTPException(status_code=500, detail="Error leyendo agenda cliente")

# Mantenemos este endpoint legacy por compatibilidad
@app.get("/api/data")
def get_dashboard_data():
    return get_agenda_ministerio()

# --- 3. ENDPOINT DE SUBIDA (PDF + EXCEL) ---
@app.post("/api/upload")
def upload_file_endpoint(file: UploadFile = File(...)):
    allowed_extensions = ('.pdf', '.xlsx', '.xls', '.csv')
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF, Excel o CSV")
    
    try:
        exito, mensaje = procesar_archivo_subido(file)
        if exito:
            return {"status": "ok", "message": mensaje}
        else:
            raise HTTPException(status_code=500, detail=mensaje)
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error upload no controlado: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error procesando el archivo")

# --- 4. ENDPOINT DE VOZ ---
@app.post("/upload-audio/") 
def upload_audio_endpoint(file: UploadFile = File(...)):
    # logger.info(f"Recibiendo audio: {file.filename}") 
    if not file.content_type.startswith('audio/'):
         raise HTTPException(status_code=400, detail="El archivo debe ser audio")
    
    try:
        texto_transcrito = procesar_audio_gemini(file)
        # Guardado automático silencioso
        if texto_transcrito:
            guardar_acta(transcripcion=texto_transcrito, resumen=None)

        return {
            "mensaje": "Procesamiento exitoso",
            "transcripcion": texto_transcrito
        }
    except Exception as e:
        logger.error(f"Error audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 5. ENDPOINTS DE HISTORIAL ---
@app.get("/actas")
def get_actas():
    try:
        return obtener_historial_actas()
    except Exception as e:
        logger.error(f"Error fetching actas: {e}")
        return []

@app.delete("/actas/{id_acta}")
def delete_acta_endpoint(id_acta: int):
    try:
        exito = borrar_acta(id_acta)
        if exito: return {"status": "ok", "message": "Eliminado"}
        raise HTTPException(status_code=404, detail="No encontrado")
    except Exception as e:
        logger.error(f"Error delete: {e}")
        raise HTTPException(status_code=500, detail="Error interno")