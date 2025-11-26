import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Importamos el agente y la función de datos crudos
from agents.main_agent import get_agent_response
from tools.dashboard import obtener_datos_raw

# Inicialización de la aplicación
app = FastAPI()

# --- REGLA DE SEGURIDAD CORS (CRÍTICA PARA CONECTAR RENDER Y VERCEL) ---
# **¡IMPORTANTE!** Reemplaza 'TU_DOMINIO_VERCEL.vercel.app' con la URL real de tu frontend.
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://pruebamincyt.vercel.app",
    "https://pruebamincyt.onrender.com",
    # --- AGREGA ESTAS LÍNEAS ---
    "https://www.pruebasmincyt.ar",
    "https://pruebasmincyt.ar", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    # El regex está bien para Vercel, pero NO cubre tu dominio .ar
    allow_origin_regex=r"https://.*\.vercel\.app", 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --- FIN CORS ---

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)

@app.get("/")
def read_root():
    return {"status": "online", "system": "MinCYT Dashboard & AI"}

# --- ENDPOINT 1: EL CHATBOT (IA) ---
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        respuesta = get_agent_response(request.message)
        return {"response": respuesta}
    except Exception as e:
        print(f"❌ Error en chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Error procesando la solicitud")

# --- ENDPOINT 2: LA TABLA VISUAL (Datos) ---
@app.get("/api/data")
def get_dashboard_data():
    """Devuelve el JSON completo para pintar la tabla en el Frontend"""
    datos = obtener_datos_raw()
    return datos

# --- ENDPOINT 3: SINCRONIZAR (Botón verde) ---
@app.post("/api/sync")
def sync_dashboard():
    """
    Sincronizar es simplemente confirmar que el servicio está activo.
    """
    return {"status": "ok", "msg": "Datos actualizados desde Google Sheets"}