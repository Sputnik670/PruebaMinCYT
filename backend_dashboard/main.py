# backend/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- CAMBIO CLAVE AQUÍ ---
# Ya no importamos de "agent", sino de la nueva carpeta "agents.main_agent"
from agents.main_agent import get_agent_response 

app = FastAPI()

# Configuración de seguridad (CORS) para que Vercel pueda entrar
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
    return {"status": "online", "system": "MinCYT AI Agent Modular v2"}

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    # Esta función ahora llama al código limpio que está en /agents
    respuesta = get_agent_response(request.message)
    return {"response": respuesta}