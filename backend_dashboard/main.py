# Archivo: backend/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

# Importamos la función del agente que creamos en el otro archivo
from agent import get_agent_response

app = FastAPI()

# --- CONFIGURACIÓN DE CORS ---
# Esto es vital para que Vercel (frontend) pueda comunicarse con Render (backend)
# "allow_origins=['*']" permite conexiones desde cualquier lugar.
# Para producción estricta se pondría solo la URL de Vercel, pero para probar déjalo así.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelo de datos para recibir el mensaje del usuario
class ChatRequest(BaseModel):
    message: str

# 1. Endpoint de prueba (Health Check)
# Sirve para saber si el servidor de Render arrancó bien.
@app.get("/")
def read_root():
    return {"status": "online", "message": "Backend del Agente MinCYT funcionando 🚀"}

# 2. Endpoint del Chatbot
# Aquí es donde el frontend manda el mensaje y el Agente responde.
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    print(f"📩 Mensaje recibido: {request.message}")
    
    try:
        # Llamamos a tu Agente (que vive en agent.py)
        respuesta = get_agent_response(request.message)
        print(f"🤖 Respuesta generada: {respuesta}")
        
        return {"response": respuesta}
    
    except Exception as e:
        print(f"❌ Error procesando el mensaje: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Nota: Si tenías otros endpoints específicos para gráficos (que no sean del chat),
# tendrías que agregarlos aquí abajo. Pero para el Chatbot, esto es todo lo que necesitas.