from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Importamos el agente y AHORA TAMBIÉN la función de datos crudos
from agents.main_agent import get_agent_response
from tools.dashboard import obtener_datos_raw

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def read_root():
    return {"status": "online", "system": "MinCYT Dashboard & AI"}

# --- ENDPOINT 1: EL CHATBOT (IA) ---
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    respuesta = get_agent_response(request.message)
    return {"response": respuesta}

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
    Como ahora leemos en tiempo real de Google Sheets, 
    'sincronizar' es simplemente confirmar que está todo ok.
    """
    # Aquí podrías agregar lógica de caché si quisieras en el futuro
    return {"status": "ok", "msg": "Datos actualizados desde Google Sheets"}