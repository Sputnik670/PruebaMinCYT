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

# --- FUNCIÓN IA DETECTIVE (Diagnóstico Extremo) ---
def consultar_gemini_debug(prompt):
    # 1. Verificación de Llave
    if not GEMINI_API_KEY:
        return "❌ Error: La variable GEMINI_API_KEY está vacía o no existe."
    
    # Ocultamos la llave pero mostramos su "huella digital" para ver si está rota
    largo = len(GEMINI_API_KEY)
    final = GEMINI_API_KEY[-4:] if largo > 4 else "????",
    debug_info = f"🔑 Llave detectada: Longitud {largo}, termina en '...{final}'"

    # 2. Intentos con múltiples versiones y modelos
    # A veces v1beta falla y v1 funciona, o viceversa.
    combinaciones = [
        ("v1beta", "gemini-1.5-flash"),
        ("v1", "gemini-1.5-flash"),
        ("v1beta", "gemini-pro"),
        ("v1", "gemini-pro")
    ]
    
    log_errores = []

    for version, modelo in combinaciones:
        url = f"https://generativelanguage.googleapis.com/{version}/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{"parts": [{"text": prompt}]}]
        }
        
        try:
            response = requests.post(url, json=data, headers=headers, timeout=10)
            
            # ¡ÉXITO!
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            
            # Capturar el error exacto que manda Google
            mensaje_error = response.text
            log_errores.append(f"❌ [{version}/{modelo}] Status {response.status_code}: {mensaje_error}")

        except Exception as e:
            log_errores.append(f"💥 Excepción conectando a {version}: {str(e)}")

    # Si llegamos acá, nada funcionó. Devolvemos el reporte forense.
    return f"""
    🚨 REPORTE DE FALLO TOTAL 🚨
    
    {debug_info}
    
    Errores recibidos de Google:
    {chr(10).join(log_errores)}
    """

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

    prompt = f"""
    Eres el Asistente MinCYT.
    CALENDARIO (DB): {ctx_db}
    WEB: {ctx_web}
    PREGUNTA: "{pregunta}"
    """
    
    # Usamos la función detective
    respuesta_ia = consultar_gemini_debug(prompt)
    return {"respuesta": respuesta_ia}