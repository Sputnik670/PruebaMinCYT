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

# --- VARIABLES ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# --- CONFIGURACIÓN GOOGLE SHEETS ---
SHEETS = {
    "ventas": "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv",
    "bitacora": "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv",
    "calendario": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"
}

# --- CONEXIÓN SUPABASE ---
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except: pass

# --- IA ---
model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    safety = {HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH}
    try: model = genai.GenerativeModel('gemini-1.5-flash', safety_settings=safety)
    except: pass

# --- LÓGICA DE LIMPIEZA ROBUSTA (VERSION ACTUALIZADA) 🪄 ---
def normalizar_dataframe(df, tabla_destino):
    """
    Traduce las columnas del Excel a las columnas exactas de Supabase.
    """
    # 1. Limpieza básica de cabeceras (minusculas y sin espacios extra)
    df.columns = [c.lower().strip() for c in df.columns]
    
    # 2. DICCIONARIO DE TRADUCCIÓN (Aquí agregamos tus columnas nuevas)
    traducciones = {
        # VENTAS (Mantenemos las anteriores por si acaso)
        "nombre": "proyecto", "proyecto": "proyecto",
        "monto": "monto", "inversion": "monto",
        "responsable": "responsable", "estado": "estado",
        
        # BITACORA
        "tarea": "tarea", "actividad": "tarea",
        "tipo": "tipo", "duración (hs)": "duracion", "duracion": "duracion",
        
        # --- CALENDARIO (ACTUALIZADO SEGÚN TU IMAGEN) ---
        "título": "evento", "titulo": "evento",  # Tu Excel dice 'Título' -> DB 'evento'
        "fecha inicio": "fecha",                 # Tu Excel dice 'Fecha inicio' -> DB 'fecha'
        "lugar": "pais",                         # Tu Excel dice 'Lugar' -> DB 'pais'
        "nac/intl": "importancia",               # Usamos 'Nac/Intl' para llenar 'importancia'
        "organizador": "descripcion"             # (Opcional) Si tuvieras campo descripcion
    }
    
    # Renombrar columnas
    df.rename(columns=traducciones, inplace=True)
    
    # 3. Filtrar solo columnas válidas para Supabase
    columnas_validas = ["fecha", "proyecto", "monto", "estado", "responsable", "tarea", "tipo", "duracion", "evento", "pais", "importancia"]
    df = df[[c for c in df.columns if c in columnas_validas]]
    
    # 4. Limpieza de datos
    df = df.replace({np.nan: None})
    
    # Forzar formato de fecha día primero (DD/MM/YYYY)
    if 'fecha' in df.columns:
        df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
        
    return df

@app.post("/api/sync")
def sincronizar_sheets():
    if not supabase: return {"status": "error", "msg": "Falta Supabase Key"}
    
    log = []
    for tabla, url in SHEETS.items():
        try:
            if "TU_LINK" in url: continue
            
            # 1. Leer
            r = requests.get(url)
            r.encoding = 'utf-8' # Forzar UTF-8 para acentos
            df = pd.read_csv(io.BytesIO(r.content))
            
            # 2. Normalizar
            df_limpio = normalizar_dataframe(df, tabla)
            
            if df_limpio.empty:
                log.append(f"⚠️ {tabla}: Sin columnas coincidentes.")
                continue

            datos_dict = df_limpio.to_dict(orient='records')
            
            # 3. Escribir (Borrón y Cuenta Nueva)
            supabase.table(tabla).delete().neq("id", 0).execute() 
            if datos_dict:
                supabase.table(tabla).insert(datos_dict).execute()
            
            log.append(f"✅ {tabla}: {len(datos_dict)} filas guardadas.")
            
        except Exception as e:
            log.append(f"❌ Error {tabla}: {str(e)}")
            print(f"SYNC ERROR {tabla}: {e}")

    return {"status": "ok", "detalles": log}

# --- RESTO DE ENDPOINTS ---
def get_tabla(nombre):
    if not supabase: return []
    try: return supabase.table(nombre).select("*").limit(100).execute().data
    except: return []

@app.get("/api/dashboard")
def get_dashboard():
    return {
        "bitacora": get_tabla("bitacora"),
        "ventas_tabla": get_tabla("ventas"),
        "extra_tabla": get_tabla("calendario"),
        "tendencia_grafico": []
    }

@app.post("/api/chat")
async def chat(pregunta: str = Form(...), file: UploadFile = File(None)):
    if not model: return {"respuesta": "Error IA"}
    
    ctx_dash = ""
    try:
        v = get_tabla("ventas")
        c = get_tabla("calendario")
        if c: ctx_dash += f"\nCALENDARIO:\n{tabulate(c, headers='keys')}\n"
        if v: ctx_dash += f"\nVENTAS:\n{tabulate(v, headers='keys')}\n"
    except: pass

    txt_web = ""
    if TAVILY_API_KEY:
        try:
            t = TavilyClient(api_key=TAVILY_API_KEY)
            res = t.search(pregunta)
            txt_web = str(res.get('results'))
        except: pass

    prompt = f"""Asistente MinCYT.
    DATOS INTERNOS: {ctx_dash}
    WEB: {txt_web}
    PREGUNTA: {pregunta}"""
    
    try:
        res = model.generate_content(prompt)
        return {"respuesta": res.text}
    except Exception as e: return {"respuesta": str(e)}