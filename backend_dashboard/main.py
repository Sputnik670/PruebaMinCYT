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

# --- TUS LLAVES (Ya configuradas en Render) ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# --- TU ÚNICO LINK DE VERDAD (Calendario) ---
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

# --- FUNCIÓN DE SINCRONIZACIÓN BLINDADA ---
@app.post("/api/sync")
def sincronizar():
    if not supabase: return {"status": "error", "msg": "Falta conexión a Supabase"}
    
    try:
        # 1. Descargar Excel
        print("Descargando Excel...")
        r = requests.get(URL_CALENDARIO)
        r.encoding = 'utf-8'
        df = pd.read_csv(io.BytesIO(r.content))
        
        # 2. Normalizar columnas (Tu Excel -> Base de Datos)
        # Convertimos todo a minúsculas y quitamos espacios
        df.columns = [c.lower().strip() for c in df.columns]
        
        # Mapeo EXACTO basado en tu imagen
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
        
        # 3. Limpiar datos (Fechas y vacíos)
        df = df.replace({np.nan: None})
        
        for col in ["fecha_inicio", "fecha_fin"]:
            if col in df.columns:
                # Forzamos que entienda DD/MM/YYYY
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')

        # 4. Guardar en Supabase (Solo columnas válidas)
        cols_validas = ["nac_intl", "titulo", "fecha_inicio", "fecha_fin", "lugar", "organizador", "pagan", "participante", "observaciones"]
        df_final = df[[c for c in df.columns if c in cols_validas]]
        
        datos = df_final.to_dict(orient='records')
        
        # Borrón y cuenta nueva
        supabase.table("calendario_internacional").delete().neq("id", 0).execute()
        if datos:
            supabase.table("calendario_internacional").insert(datos).execute()
            
        return {"status": "ok", "msg": f"¡Éxito! {len(datos)} eventos actualizados."}
        
    except Exception as e:
        print(f"Error Sync: {e}")
        return {"status": "error", "msg": str(e)}

# --- ENDPOINTS DE DATOS ---
@app.get("/api/data")
def get_data():
    if not supabase: return []
    try: 
        # Traemos todo el calendario ordenado por fecha
        return supabase.table("calendario_internacional").select("*").order("fecha_inicio", desc=False).execute().data
    except: return []

@app.post("/api/chat")
async def chat(pregunta: str = Form(...), file: UploadFile = File(None)):
    if not model: return {"respuesta": "Error: IA no disponible."}
    
    # 1. Contexto del Calendario (Base de Datos)
    data = get_data()
    ctx_db = "(El calendario está vacío. Pide actualizar datos)"
    if data:
        # Usamos tabulate para que la IA entienda la estructura de filas y columnas
        ctx_db = tabulate(data, headers="keys", tablefmt="github")
    
    # 2. Contexto Web (Si aplica)
    ctx_web = ""
    if TAVILY_API_KEY:
        try: ctx_web = str(TavilyClient(api_key=TAVILY_API_KEY).search(pregunta, max_results=2))
        except: pass

    # 3. Contexto PDF (Si hay archivo)
    ctx_pdf = ""
    if file:
        try:
            content = await file.read()
            pdf = pypdf.PdfReader(io.BytesIO(content))
            for p in pdf.pages[:5]: ctx_pdf += p.extract_text()
        except: pass

    prompt = f"""
    Eres el Asistente Oficial del MinCYT.
    
    TU FUENTE DE VERDAD (CALENDARIO INTERNACIONAL):
    {ctx_db}
    
    OTRAS FUENTES:
    - PDF Adjunto: {ctx_pdf}
    - Internet: {ctx_web}
    
    PREGUNTA DEL USUARIO: {pregunta}
    
    INSTRUCCIONES:
    - Si preguntan por eventos, fechas o viajes, BASATE EXCLUSIVAMENTE en la tabla de 'CALENDARIO INTERNACIONAL' provista arriba.
    - Si la tabla dice 'pagan: NO', avísalo.
    - Sé preciso con las fechas.
    """
    
    try:
        res = model.generate_content(prompt)
        return {"respuesta": res.text}
    except Exception as e: return {"respuesta": str(e)}