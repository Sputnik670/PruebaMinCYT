import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import io
import os
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import pypdf
from tavily import TavilyClient
from tabulate import tabulate 
from supabase import create_client, Client
import sys

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- VARIABLES DE ENTORNO ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# --- CONEXIÓN SUPABASE ---
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Base de Datos Supabase: CONECTADA")
    except Exception as e:
        print(f"❌ Error conectando Supabase: {e}")

# --- IA ---
model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    safety = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }
    candidatos = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
    for nombre in candidatos:
        try:
            model = genai.GenerativeModel(nombre, safety_settings=safety)
            break
        except: continue

# --- FUNCIONES DE BASE DE DATOS ---
def obtener_datos_tabla(nombre_tabla, limite=50):
    """Trae datos de Supabase en lugar de CSV."""
    if not supabase: return pd.DataFrame()
    try:
        response = supabase.table(nombre_tabla).select("*").limit(limite).execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        print(f"⚠️ Error tabla {nombre_tabla}: {e}")
        return pd.DataFrame()

def guardar_historial(pregunta, respuesta, fuente):
    """Guarda la conversación."""
    if not supabase: return
    try:
        supabase.table("historial_chat").insert({
            "pregunta": pregunta,
            "respuesta": respuesta,
            "fuente_usada": fuente
        }).execute()
    except: pass

# --- CONTEXTO ---
def obtener_contexto_dashboard():
    texto = ""
    # Calendario
    df_cal = obtener_datos_tabla("calendario")
    if not df_cal.empty:
        texto += f"\n### 📅 CALENDARIO:\n{df_cal.to_markdown(index=False)}\n"
    # Ventas
    df_ven = obtener_datos_tabla("ventas")
    if not df_ven.empty:
        texto += f"\n### 💰 VENTAS:\n{df_ven.tail(15).to_markdown(index=False)}\n"
    # Bitácora
    df_bit = obtener_datos_tabla("bitacora")
    if not df_bit.empty:
        texto += f"\n### ⏱️ BITÁCORA:\n{df_bit.head(15).to_markdown(index=False)}\n"
    
    return texto if texto else "(Sin datos DB)"

async def obtener_contexto_pdf(file: UploadFile):
    if not file: return ""
    try:
        content = await file.read()
        pdf = pypdf.PdfReader(io.BytesIO(content))
        txt = f"\n### 📄 PDF ({file.filename}):\n"
        for p in pdf.pages[:5]: txt += p.extract_text() + "\n"
        return txt
    except: return ""

def obtener_contexto_web(consulta):
    if not TAVILY_API_KEY: return ""
    try:
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        resp = tavily.search(query=consulta, search_depth="basic", max_results=3)
        txt = "\n### 🌍 INTERNET:\n"
        for r in resp.get('results', []): txt += f"- {r.get('title')}: {r.get('content')}\n"
        return txt
    except: return ""

# --- ENDPOINTS ---
@app.get("/api/dashboard")
def get_dashboard_data():
    # Convierte la data de Supabase a JSON para el frontend
    return {
        "bitacora": obtener_datos_tabla("bitacora").to_dict(orient="records"),
        "ventas_tabla": obtener_datos_tabla("ventas").to_dict(orient="records"),
        "extra_tabla": obtener_datos_tabla("calendario").to_dict(orient="records"),
        "tendencia_grafico": [] 
    }

@app.post("/api/chat")
async def chat_endpoint(pregunta: str = Form(...), file: UploadFile = File(None)):
    if not model: return {"respuesta": "Error IA"}

    ctx_dash = obtener_contexto_dashboard()
    ctx_pdf = await obtener_contexto_pdf(file)
    ctx_web = obtener_contexto_web(pregunta)
    
    # Detectar fuente para el log
    fuente = "General"
    if "Sin datos" not in ctx_dash: fuente = "DB"
    if ctx_pdf: fuente = "PDF"
    if "INTERNET" in ctx_web: fuente += "+Web"

    prompt = f"""
    Eres el Asistente MinCYT con acceso a Base de Datos en vivo.
    
    1. [DB] DATOS INTERNOS:
    {ctx_dash}
    2. [PDF] ADJUNTO:
    {ctx_pdf}
    3. [WEB] INTERNET:
    {ctx_web}
    
    PREGUNTA: "{pregunta}"
    """

    try:
        res = model.generate_content(prompt)
        # Guardamos en Supabase
        guardar_historial(pregunta, res.text, fuente)
        return {"respuesta": res.text}
    except Exception as e:
        return {"respuesta": f"Error: {e}"}