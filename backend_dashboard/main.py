import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import io
import os
import requests
import pypdf
from tavily import TavilyClient
from tabulate import tabulate 
from supabase import create_client, Client
import numpy as np

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- VARIABLES ---
# Esta variable AHORA tiene tu llave de OpenRouter (sk-or-v1...)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

URL_CALENDARIO = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"

# --- CONEXIÓN SUPABASE ---
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try: supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except: pass

# --- FUNCIÓN IA ROBUSTA (VÍA OPENROUTER) ---
def consultar_ia(prompt):
    if not GEMINI_API_KEY:
        return "❌ Error: Falta API Key (OpenRouter)."

    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GEMINI_API_KEY}",
        "Content-Type": "application/json",
        # Opcional: Ayuda a OpenRouter a identificar tu app
        "HTTP-Referer": "https://render.com",
        "X-Title": "MinCYT Dashboard"
    }
    
    # CAMBIO CLAVE: Usamos 'gemini-flash-1.5' que es más estable y barato
    data = {
        "model": "google/gemini-flash-1.5", 
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            # Si falla Flash, probamos un fallback automático a Pro
            print(f"⚠️ Flash falló ({response.status_code}), intentando con Pro...")
            data["model"] = "google/gemini-pro-1.5"
            response_retry = requests.post(url, json=data, headers=headers, timeout=30)
            
            if response_retry.status_code == 200:
                return response_retry.json()['choices'][0]['message']['content']
            
            return f"Error OpenRouter: {response.text}"
            
    except Exception as e:
        return f"Error de conexión: {str(e)}"

# --- SINCRONIZACIÓN ---
@app.post("/api/sync")
def sincronizar():
    if not supabase: return {"status": "error", "msg": "Falta conexión a Supabase"}
    try:
        print("📥 Descargando Excel...")
        r = requests.get(URL_CALENDARIO)
        r.encoding = 'utf-8'
        df = pd.read_csv(io.BytesIO(r.content))
        
        df.columns = [c.lower().strip() for c in df.columns]
        traduccion = {
            "nac/intl": "nac_intl", "título": "titulo", "titulo": "titulo",
            "fecha inicio": "fecha_inicio", "fecha fin": "fecha_fin",
            "lugar": "lugar", "organizador": "organizador",
            "¿pagan?": "pagan", "pagan": "pagan", "pagan?": "pagan",
            "participante": "participante", "observaciones": "observaciones"
        }
        df.rename(columns=traduccion, inplace=True)
        
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df = df.where(pd.notnull(df), None)
        
        for col in ["fecha_inicio", "fecha_fin"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
                df[col] = df[col].replace({np.nan: None})

        cols = ["nac_intl", "titulo", "fecha_inicio", "fecha_fin", "lugar", "organizador", "pagan", "participante", "observaciones"]
        df = df[[c for c in df.columns if c in cols]]
        datos = df.to_dict(orient='records')
        
        supabase.table("calendario_internacional").delete().neq("id", 0).execute()
        if datos: supabase.table("calendario_internacional").insert(datos).execute()
            
        return {"status": "ok", "msg": f"¡Éxito! {len(datos)} eventos actualizados."}
    except Exception as e:
        return {"status": "error", "msg": f"Error Sync: {str(e)}"}

# --- ENDPOINTS ---
@app.get("/api/data")
def get_data():
    if not supabase: return []
    try: return supabase.table("calendario_internacional").select("*").order("fecha_inicio", desc=False).execute().data
    except: return []

@app.post("/api/chat")
async def chat(pregunta: str = Form(...), file: UploadFile = File(None)):
    # 1. Contexto Datos
    data = get_data()
    ctx_db = tabulate(data, headers="keys", tablefmt="github") if data else "(Sin datos)"
    
    # 2. Web
    ctx_web = ""
    if TAVILY_API_KEY:
        try: 
            tavily = TavilyClient(api_key=TAVILY_API_KEY)
            res = tavily.search(query=pregunta, search_depth="advanced", max_results=3)
            for r in res.get('results', []):
                ctx_web += f"- {r['title']}: {r['content']}\n"
        except: pass

    # 3. PDF
    ctx_pdf = ""
    if file:
        try:
            content = await file.read()
            pdf = pypdf.PdfReader(io.BytesIO(content))
            for p in pdf.pages[:5]: ctx_pdf += p.extract_text()
        except: pass

    prompt = f"""
    Eres el Asistente MinCYT.
    CALENDARIO (DB): {ctx_db}
    WEB: {ctx_web}
    PDF: {ctx_pdf}
    PREGUNTA: "{pregunta}"
    """
    
    respuesta = consultar_ia(prompt)
    return {"respuesta": respuesta}