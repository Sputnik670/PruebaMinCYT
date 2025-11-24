import os
import io
import pandas as pd
import numpy as np
import requests
import pypdf
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from tavily import TavilyClient
from tabulate import tabulate
from groq import Groq  # <-- CAMBIO DE MOTOR

app = FastAPI(title="MinCYT Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURACIÓN ---
# IMPORTANTE: En Render, pon tu llave de Groq en la variable GEMINI_API_KEY
# (o crea una variable GROQ_API_KEY y cámbialo aquí)
GROQ_API_KEY = os.environ.get("GEMINI_API_KEY") 
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
URL_CALENDARIO = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"

# Clientes
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try: supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except: pass

client_groq = None
if GROQ_API_KEY:
    client_groq = Groq(api_key=GROQ_API_KEY)

# --- 1. SINCRONIZACIÓN ---
@app.post("/api/sync")
def sincronizar_datos():
    if not supabase: return {"status": "error", "msg": "Falta conexión DB"}
    try:
        r = requests.get(URL_CALENDARIO, timeout=10)
        r.encoding = 'utf-8'
        df = pd.read_csv(io.BytesIO(r.content))
        
        df.columns = [c.lower().strip() for c in df.columns]
        mapeo = {
            "nac/intl": "nac_intl", "título": "titulo", "titulo": "titulo",
            "fecha inicio": "fecha_inicio", "fecha fin": "fecha_fin",
            "lugar": "lugar", "organizador": "organizador",
            "¿pagan?": "pagan", "pagan": "pagan",
            "participante": "participante", "observaciones": "observaciones"
        }
        df.rename(columns=mapeo, inplace=True)
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df = df.where(pd.notnull(df), None)
        
        for col in ["fecha_inicio", "fecha_fin"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
                df[col] = df[col].replace({np.nan: None})

        cols = [c for c in df.columns if c in list(mapeo.values())]
        registros = df[cols].to_dict(orient='records')
        
        supabase.table("calendario_internacional").delete().neq("id", 0).execute()
        if registros: supabase.table("calendario_internacional").insert(registros).execute()
            
        return {"status": "ok", "msg": f"✅ {len(registros)} eventos sincronizados."}
    except Exception as e:
        return {"status": "error", "msg": f"Error: {str(e)}"}

# --- 2. DATOS ---
@app.get("/api/data")
def obtener_datos():
    if not supabase: return []
    try: return supabase.table("calendario_internacional").select("*").order("fecha_inicio", desc=False).execute().data
    except: return []

# --- 3. CHATBOT (CON GROQ / LLAMA 3) ---
@app.post("/api/chat")
async def chat_endpoint(pregunta: str = Form(...), file: UploadFile = File(None)):
    if not client_groq: return {"respuesta": "❌ Error: API Key de Groq no configurada."}

    # Contextos
    ctx_db = "(Sin datos)"
    try:
        data = obtener_datos()
        if data: ctx_db = tabulate(data, headers="keys", tablefmt="github")
    except: pass

    ctx_web = ""
    if TAVILY_API_KEY:
        try:
            t = TavilyClient(api_key=TAVILY_API_KEY)
            res = t.search(query=pregunta, search_depth="advanced", max_results=3)
            ctx_web = "\n".join([f"- {r['title']}: {r['content']}" for r in res.get('results', [])])
        except: pass

    ctx_pdf = ""
    if file:
        try:
            c = await file.read()
            pdf = pypdf.PdfReader(io.BytesIO(c))
            ctx_pdf = "\n".join([p.extract_text() for p in pdf.pages[:5]])
        except: pass

    # Prompt
    sistema = """Eres el Asistente Inteligente del MinCYT.
    
    FUENTES DE INFORMACIÓN:
    1. [DB] CALENDARIO OFICIAL: Usa esto prioritariamente para eventos y viajes.
    2. [WEB] INTERNET: Usa esto para noticias, deportes o contexto general.
    3. [PDF] ADJUNTO: Usa esto si el usuario pregunta por el archivo.
    
    INSTRUCCIONES:
    - Responde de forma directa y profesional en español.
    - Cita la fuente de tu información (ej: "Según el calendario...", "Según internet...").
    """
    
    usuario = f"DATOS INTERNOS: {ctx_db}\nWEB: {ctx_web}\nPDF: {ctx_pdf}\nPREGUNTA: {pregunta}"

    try:
        # Usamos Llama 3 70b, que es muy potente y rápido en Groq
        completion = client_groq.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario}
            ],
            temperature=0.5,
            max_tokens=1024,
        )
        return {"respuesta": completion.choices[0].message.content}
    except Exception as e:
        return {"respuesta": f"❌ Error Groq: {str(e)}"}