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

# --- VARIABLES DE ENTORNO ---
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

# --- CONFIGURACIÓN IA (ESTRATEGIA ROBUSTA) ---
model = None

def configurar_modelo():
    """Busca y conecta automáticamente con el mejor modelo disponible."""
    if not GEMINI_API_KEY:
        print("⚠️ Falta GEMINI_API_KEY")
        return None

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Configuración de seguridad permisiva
        safety = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }

        # Lista de intentos en orden de preferencia
        candidatos = [
            'gemini-1.5-flash',
            'models/gemini-1.5-flash',
            'gemini-1.5-pro',
            'gemini-pro',
            'models/gemini-pro'
        ]

        print("🔍 Buscando modelo Gemini compatible...")
        for nombre in candidatos:
            try:
                m = genai.GenerativeModel(nombre, safety_settings=safety)
                # Prueba rápida de conexión
                m.generate_content("Ping")
                print(f"✅ IA Conectada exitosamente con: {nombre}")
                return m
            except:
                continue
        
        print("❌ No se pudo conectar con ningún modelo estándar.")
        return None

    except Exception as e:
        print(f"Error fatal configurando IA: {e}")
        return None

# Inicializamos el modelo al arrancar
model = configurar_modelo()

# --- SINCRONIZACIÓN (CALENDARIO) ---
@app.post("/api/sync")
def sincronizar():
    if not supabase: return {"status": "error", "msg": "Falta conexión a Supabase"}
    
    try:
        print("📥 Descargando Excel...")
        r = requests.get(URL_CALENDARIO)
        r.encoding = 'utf-8'
        df = pd.read_csv(io.BytesIO(r.content))
        
        # Normalización
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
        
        # Limpieza anti-errores
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df = df.where(pd.notnull(df), None)
        
        for col in ["fecha_inicio", "fecha_fin"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
                df[col] = df[col].replace({np.nan: None})

        # Filtrar y Guardar
        cols_validas = ["nac_intl", "titulo", "fecha_inicio", "fecha_fin", "lugar", "organizador", "pagan", "participante", "observaciones"]
        df_final = df[[c for c in df.columns if c in cols_validas]]
        
        datos = df_final.to_dict(orient='records')
        
        supabase.table("calendario_internacional").delete().neq("id", 0).execute()
        if datos:
            supabase.table("calendario_internacional").insert(datos).execute()
            
        return {"status": "ok", "msg": f"¡Éxito! {len(datos)} eventos actualizados."}
        
    except Exception as e:
        print(f"❌ Error Sync: {e}")
        return {"status": "error", "msg": f"Error procesando datos: {str(e)}"}

# --- ENDPOINTS ---
@app.get("/api/data")
def get_data():
    if not supabase: return []
    try: 
        return supabase.table("calendario_internacional").select("*").order("fecha_inicio", desc=False).execute().data
    except: return []

@app.post("/api/chat")
async def chat(pregunta: str = Form(...), file: UploadFile = File(None)):
    global model
    
    # Reintento de conexión si falló al inicio
    if not model:
        print("🔄 Reintentando conectar IA...")
        model = configurar_modelo()
    
    if not model: return {"respuesta": "Error: No se pudo conectar con la IA de Google. Revisa los logs del servidor."}
    
    # Contexto Datos
    data = get_data()
    ctx_db = tabulate(data, headers="keys", tablefmt="github") if data else "(Sin datos en Calendario)"
    
    # Contexto Web
    ctx_web = ""
    if TAVILY_API_KEY:
        try: ctx_web = str(TavilyClient(api_key=TAVILY_API_KEY).search(pregunta, max_results=2))
        except: pass

    # Contexto PDF
    ctx_pdf = ""
    if file:
        try:
            content = await file.read()
            pdf = pypdf.PdfReader(io.BytesIO(content))
            for p in pdf.pages[:5]: ctx_pdf += p.extract_text()
        except: pass

    prompt = f"""
    Eres el Asistente Oficial del MinCYT.
    
    FUENTE 1: CALENDARIO INTERNACIONAL (Base de Datos):
    {ctx_db}
    
    FUENTE 2: INTERNET:
    {ctx_web}
    
    FUENTE 3: PDF ADJUNTO:
    {ctx_pdf}
    
    PREGUNTA: {pregunta}
    
    INSTRUCCIONES:
    - Si preguntan por eventos, usa la FUENTE 1.
    - Si hay PDF, úsalo.
    - Sé directo y útil.
    """
    
    try:
        res = model.generate_content(prompt)
        return {"respuesta": res.text}
    except Exception as e: return {"respuesta": f"Error generando respuesta: {str(e)}"}