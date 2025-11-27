import os
from fastapi import FastAPI, HTTPException, UploadFile, File 
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.main_agent import get_agent_response
from tools.dashboard import obtener_datos_raw
from tools.docs import procesar_pdf_subido
from tools.audio import procesar_audio_gemini

app = FastAPI()

# --- REGLA DE SEGURIDAD CORS: MODO PERMISIVO ("El Martillo") ---
# En lugar de una lista específica que puede fallar, usamos un Regex que acepta TODO.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",  # <--- ESTO ES LA CLAVE: Acepta cualquier origen
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --------------------------------------------------------------
# --- NUEVO ENDPOINT DE AUDIO ---
@app.post("/api/voice")
async def voice_endpoint(file: UploadFile = File(...)):
    """
    Endpoint para recibir blobs de audio del micrófono,
    transcribirlos y traducirlos.
    """
    if not file.content_type.startswith('audio/'):
         raise HTTPException(status_code=400, detail="El archivo debe ser audio")
    
    texto_transcrito = procesar_audio_gemini(file)
    return {"text": texto_transcrito}

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def read_root():
    return {"status": "online", "system": "MinCYT Dashboard & AI"}

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    respuesta = get_agent_response(request.message)
    return {"response": respuesta}

@app.get("/api/data")
def get_dashboard_data():
    datos = obtener_datos_raw()
    return datos

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF")
    
    exito, mensaje = procesar_pdf_subido(file)
    
    if exito:
        return {"status": "ok", "message": mensaje}
    else:
        raise HTTPException(status_code=500, detail=mensaje)