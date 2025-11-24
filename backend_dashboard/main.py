# Archivo: backend/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import get_agent_response
from config import supabase

app = FastAPI()  # ← Esto debe estar antes de los endpoints

# Modelo para requests al chatbot
class ChatRequest(BaseModel):
    message: str

# Endpoint de prueba de estado
@app.get("/")
def read_root():
    return {"status": "online"}

# Endpoint del Chatbot
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        respuesta = get_agent_response(request.message)
        return {"response": respuesta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Nuevo endpoint: consulta Supabase
@app.get("/api/calendario")
async def get_calendario():
    try:
        result = supabase.table("calendario_internacional").select("*").execute()
        return result.data
    except Exception as e:
        return {"error": str(e)}
