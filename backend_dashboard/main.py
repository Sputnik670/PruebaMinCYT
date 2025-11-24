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
from openai import OpenAI

app = FastAPI(title="MinCYT Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- VARIABLES ---
OPENROUTER_API_KEY = os.environ.get("GEMINI_API_KEY") 
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
URL_CALENDARIO = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"

# Clientes
supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try: supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except: pass

client_ia = None
if OPENROUTER_API_KEY:
    client_ia = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

# --- SINCRONIZACIÓN ---
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

# --- DATOS ---
@app.get("/api/data")
def obtener_datos():
    if not supabase: return []
    try: return supabase.table("calendario_internacional").select("*").order("fecha_inicio", desc=False).execute().data
    except: return []

# --- CHATBOT ---
@app.post("/api/chat")
async def chat_endpoint(pregunta: str = Form(...), file: UploadFile = File(None)):
    if not client_ia: return {"respuesta": "❌ Error: Sistema de IA desconectado."}

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

    sistema = """Eres el Asistente Inteligente del MinCYT.
    FUENTES:
    1. [DB] CALENDARIO OFICIAL: Verdad absoluta para eventos/viajes.
    2. [WEB] INTERNET: Para noticias, deportes y actualidad.
    3. [PDF] DOCUMENTO: Si el usuario sube uno.
    
    INSTRUCCIONES:
    - Prioriza la información del CALENDARIO si preguntan por eventos.
    - Si preguntan algo externo (clima, deportes), usa INTERNET.
    """
    
    usuario = f"DATOS: {ctx_db}\nWEB: {ctx_web}\nPDF: {ctx_pdf}\nPREGUNTA: {pregunta}"

    # LISTA DE MODELOS ESTABLES (Si falla uno, prueba el otro)
    modelos = [
        "google/gemini-flash-1.5",      # El más barato y rápido oficial
        "google/gemini-pro-1.5",        # El más potente
        "google/gemini-2.0-flash-exp:free" # El experimental (solo por si acaso)
    ]
    
    errores = []
    for modelo in modelos:
        try:
            print(f"🤖 Probando {modelo}...")
            completion = client_ia.chat.completions.create(
                model=modelo,
                messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
                extra_headers={"HTTP-Referer": "https://render.com", "X-Title": "MinCYT"}
            )
            return {"respuesta": completion.choices[0].message.content}
        except Exception as e:
            print(f"⚠️ Falló {modelo}: {e}")
            errores.append(f"{modelo}: {str(e)}")
            continue
            
    return {"respuesta": f"❌ Error de IA. Detalles: {'; '.join(errores)}"}