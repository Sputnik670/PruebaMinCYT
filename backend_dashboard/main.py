import os
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.main_agent import get_agent_response
from tools.dashboard import obtener_datos_raw
from tools.docs import procesar_pdf_subido # <--- NUEVO IMPORT

app = FastAPI()

# --- CONFIGURACIÓN CORS (Mantenemos la que ya funciona) ---
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://pruebamincyt.vercel.app",
    "https://pruebamincyt.onrender.com",
    "https://www.pruebamincyt.ar",
    "https://pruebamincyt.ar",
    "https://www.pruebasmincyt.ar",
    "https://pruebasmincyt.ar",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex="https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# --- NUEVO ENDPOINT: SUBIDA DE PDF ---
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF")
    
    exito, mensaje = procesar_pdf_subido(file)
    
    if exito:
        return {"status": "ok", "message": mensaje}
    else:
        raise HTTPException(status_code=500, detail=mensaje)