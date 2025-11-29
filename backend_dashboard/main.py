import os
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File 
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Imports de herramientas
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

app = FastAPI(title="MinCYT AI Dashboard", version="1.1.0")
print("\n" + "="*50)
print("🚀 ¡SISTEMA ACTUALIZADO! - MEMORIA DE ACTAS CARGADA")
print("Si ves esto, el código nuevo está funcionando.")
print("="*50 + "\n")

# --- SEGURIDAD CORS MEJORADA ---
# Define aquí la URL de tu frontend (ej. localhost:5173 para Vite)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # Agrega aquí la URL de Vercel/Render cuando despliegues
    # "https://mi-app-mincyt.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Mantenlo en * solo para pruebas locales rápidas, luego usa 'origins'
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)

@app.get("/")
def read_root():
    return {"status": "online", "system": "MinCYT Dashboard & AI v1.1"}

# --- 1. ENDPOINT DE CHAT (OPTIMIZADO: Sin 'async') ---
# Al quitar 'async', FastAPI ejecuta esto en un threadpool, evitando bloqueos
@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    try:
        respuesta = get_agent_response(request.message)
        return {"response": respuesta}
    except Exception as e:
        logger.error(f"❌ Error en chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del asistente")

# --- 2. ENDPOINT DE DATOS DASHBOARD ---
@app.get("/api/data")
def get_dashboard_data():
    try:
        datos = obtener_datos_raw()
        return datos
    except Exception as e:
        logger.error(f"Error datos: {e}")
        raise HTTPException(status_code=500, detail="Error de base de datos")

# --- 3. ENDPOINT DE SUBIDA PDF ---
@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF")
    
    try:
        exito, mensaje = procesar_pdf_subido(file)
        if exito:
            return {"status": "ok", "message": mensaje}
        else:
            raise HTTPException(status_code=500, detail=mensaje)
    except Exception as e:
        logger.error(f"Error upload: {e}")
        raise HTTPException(status_code=500, detail="Error al procesar archivo")

# --- 4. ENDPOINT DE VOZ (OPTIMIZADO) ---
@app.post("/upload-audio/") 
def upload_audio_endpoint(file: UploadFile = File(...)):
    logger.info(f"Recibiendo audio: {file.filename}")

    if not file.content_type.startswith('audio/'):
         raise HTTPException(status_code=400, detail="El archivo debe ser audio")
    
    try:
        # 1. Transcribir
        texto_transcrito = procesar_audio_gemini(file)
        
        # 2. Guardar en BD
        acta_guardada = None
        if texto_transcrito:
            resultado_db = guardar_acta(transcripcion=texto_transcrito, resumen=None)
            if resultado_db and len(resultado_db) > 0:
                acta_guardada = resultado_db[0]

        return {
            "mensaje": "Procesamiento exitoso",
            "transcripcion": texto_transcrito,
            "acta": acta_guardada
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
        if exito:
            return {"status": "ok", "message": "Eliminado"}
        raise HTTPException(status_code=404, detail="No encontrado")
    except Exception as e:
        logger.error(f"Error delete: {e}")
        raise HTTPException(status_code=500, detail="Error interno")