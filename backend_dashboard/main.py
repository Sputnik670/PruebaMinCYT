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
import numpy as np # Para manejar datos vacíos

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

# --- URLS DE TUS GOOGLE SHEETS (CSV PUBLISHED) ---
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

# --- IA CONFIG ---
model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    safety = {HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH}
    try: model = genai.GenerativeModel('gemini-1.5-flash', safety_settings=safety)
    except: pass

# --- LÓGICA DE SINCRONIZACIÓN (LA MAGIA) 🪄 ---
def limpiar_dataframe(df):
    """Limpia el DataFrame para que entre limpio a la base de datos."""
    # 1. Normalizar nombres de columnas (Mayúsculas a minúsculas, espacios a guiones bajos)
    df.columns = [c.lower().strip().replace(' ', '_').replace('(hs)', '').replace('ó', 'o').replace('ñ', 'n') for c in df.columns]
    
    # 2. Reemplazar NaN (vacíos) con None (NULL en SQL)
    df = df.replace({np.nan: None})
    
    # 3. Convertir fechas si existen (esto evita errores de formato)
    if 'fecha' in df.columns:
        df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce').dt.strftime('%Y-%m-%d')
        
    return df

@app.post("/api/sync")
def sincronizar_sheets():
    """Lee Google Sheets y actualiza Supabase."""
    if not supabase: return {"status": "error", "msg": "Falta configurar Supabase"}
    
    log = []
    for tabla, url in SHEETS.items():
        try:
            if "TU_LINK" in url: continue
            
            # 1. Leer de Google
            r = requests.get(url)
            df = pd.read_csv(io.BytesIO(r.content))
            
            # 2. Limpiar datos
            df_limpio = limpiar_dataframe(df)
            datos_dict = df_limpio.to_dict(orient='records')
            
            # 3. Borrar tabla vieja en Supabase (Truncate)
            # Nota: Usamos delete all. Si la tabla es gigante, esto se optimiza, pero para dashboard va bien.
            supabase.table(tabla).delete().neq("id", 0).execute() 
            
            # 4. Insertar datos nuevos
            if datos_dict:
                supabase.table(tabla).insert(datos_dict).execute()
            
            log.append(f"✅ {tabla.capitalize()}: {len(datos_dict)} filas sincronizadas.")
            
        except Exception as e:
            log.append(f"❌ Error en {tabla}: {str(e)}")
            print(f"Error sync {tabla}: {e}")

    return {"status": "ok", "detalles": log}

# --- ENDPOINTS NORMALES (LEEN DE SUPABASE, NO DE GOOGLE) ---
def get_tabla(nombre):
    if not supabase: return []
    try: return supabase.table(nombre).select("*").limit(100).execute().data
    except: return []

@app.get("/api/dashboard")
def get_dashboard():
    return {
        "bitacora": get_tabla("bitacora"),
        "ventas_tabla": get_tabla("ventas"),
        "extra_tabla": get_tabla("calendario")
    }

@app.post("/api/chat")
async def chat(pregunta: str = Form(...), file: UploadFile = File(None)):
    if not model: return {"respuesta": "Error IA"}
    
    # Contexto DB
    data_cal = get_tabla("calendario")
    data_ven = get_tabla("ventas")
    txt_db = ""
    if data_cal: txt_db += f"\nCALENDARIO:\n{tabulate(data_cal, headers='keys')}\n"
    if data_ven: txt_db += f"\nVENTAS:\n{tabulate(data_ven, headers='keys')}\n"
    
    # Contexto Web
    txt_web = ""
    if TAVILY_API_KEY:
        try: 
            t = TavilyClient(api_key=TAVILY_API_KEY)
            res = t.search(pregunta, max_results=2)
            txt_web = str(res.get('results'))
        except: pass

    # Prompt
    prompt = f"""Asistente MinCYT. 
    DATOS OFICIALES (DB): {txt_db}
    INTERNET: {txt_web}
    
    PREGUNTA: {pregunta}"""
    
    try:
        res = model.generate_content(prompt)
        # (Opcional) Guardar historial aquí
        if supabase: supabase.table("historial_chat").insert({"pregunta": pregunta, "respuesta": res.text, "fuente_usada": "Mix"}).execute()
        return {"respuesta": res.text}
    except Exception as e: return {"respuesta": str(e)}