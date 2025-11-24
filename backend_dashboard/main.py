import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import io
import os
import requests
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
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

# --- LLAVES ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

URL_CALENDARIO = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"

# --- CONEXIONES ---
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try: supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except: pass

model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    try: model = genai.GenerativeModel('gemini-1.5-flash')
    except: pass

# --- FUNCIÓN DE SINCRONIZACIÓN (VERSION FINAL) ---
@app.post("/api/sync")
def sincronizar():
    if not supabase: return {"status": "error", "msg": "Falta conexión a Supabase"}
    
    try:
        print("📥 Descargando Excel...")
        r = requests.get(URL_CALENDARIO)
        r.encoding = 'utf-8'
        df = pd.read_csv(io.BytesIO(r.content))
        
        # 1. Normalizar cabeceras
        df.columns = [c.lower().strip() for c in df.columns]
        
        traduccion = {
            "nac/intl": "nac_intl",
            "título": "titulo", "titulo": "titulo",
            "fecha inicio": "fecha_inicio",
            "fecha fin": "fecha_fin",
            "lugar": "lugar",
            "organizador": "organizador",
            "¿pagan?": "pagan", "pagan": "pagan",
            "participante": "participante",
            "observaciones": "observaciones"
        }
        df.rename(columns=traduccion, inplace=True)
        
        # 2. LIMPIEZA AGRESIVA DE DATOS (Aquí estaba el fallo)
        # Primero convertimos Infinitos a NaN
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        
        # La técnica definitiva: `where` reemplaza todo lo que sea NaN por None
        # Esto es mucho más seguro que .replace para JSON
        df = df.where(pd.notnull(df), None)
        
        # 3. Formateo de Fechas
        for col in ["fecha_inicio", "fecha_fin"]:
            if col in df.columns:
                # Coerce convierte errores en NaT (Not a Time)
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
                # Limpiamos los NaT que hayan quedado
                df[col] = df[col].replace({np.nan: None})

        # 4. Filtrar y Guardar
        cols_validas = ["nac_intl", "titulo", "fecha_inicio", "fecha_fin", "lugar", "organizador", "pagan", "participante", "observaciones"]
        df_final = df[[c for c in df.columns if c in cols_validas]]
        
        datos = df_final.to_dict(orient='records')
        
        # Borrón y cuenta nueva
        supabase.table("calendario_internacional").delete().neq("id", 0).execute()
        
        if datos:
            supabase.table("calendario_internacional").insert(datos).execute()
            
        return {"status": "ok", "msg": f"¡Éxito! {len(datos)} eventos guardados."}
        
    except Exception as e:
        print(f"❌ Error Sync: {e}")
        # Devolvemos el error detallado para verlo en el alerta del frontend
        return {"status": "error", "msg": f"Error procesando datos: {str(e)}"}

# --- ENDPOINTS DE DATOS ---
@app.get("/api/data")
def get_data():
    if not supabase: return []
    try: 
        return supabase.table("calendario_internacional").select("*").order("fecha_inicio", desc=False).execute().data
    except: return []

@app.post("/api/chat")
async def chat(pregunta: str = Form(...), file: UploadFile = File(None)):
    if not model: return {"respuesta": "Error: IA no disponible."}
    
    data = get_data()
    ctx_db = tabulate(data, headers="keys", tablefmt="github") if data else "(Sin datos)"
    
    ctx_web = ""
    if TAVILY_API_KEY:
        try: ctx_web = str(TavilyClient(api_key=TAVILY_API_KEY).search(pregunta, max_results=2))
        except: pass

    ctx_pdf = ""
    if file:
        try:
            content = await file.read()
            pdf = pypdf.PdfReader(io.BytesIO(content))
            for p in pdf.pages[:5]: ctx_pdf += p.extract_text()
        except: pass

    prompt = f"""
    Eres el Asistente Oficial del MinCYT.
    
    CALENDARIO (DB):
    {ctx_db}
    
    OTRAS FUENTES:
    - PDF: {ctx_pdf}
    - Web: {ctx_web}
    
    Consulta: {pregunta}
    """
    
    try:
        res = model.generate_content(prompt)
        return {"respuesta": res.text}
    except Exception as e: return {"respuesta": str(e)}