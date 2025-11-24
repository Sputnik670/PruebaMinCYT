import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import io
import os
import requests
# Eliminamos la dependencia de la librería problemática
# import google.generativeai as genai 
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

# --- FUNCIÓN IA DIRECTA (HTTP RAW) ---
def consultar_gemini(prompt):
    """Consulta a Gemini usando HTTP puro para evitar errores de librería."""
    if not GEMINI_API_KEY:
        return "❌ Error: Falta la API Key de Gemini."

    # Intentamos primero con el modelo rápido (Flash)
    modelos = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
    
    for modelo in modelos:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        try:
            response = requests.post(url, json=data, headers=headers, timeout=10)
            
            # Si funciona (Código 200), procesamos y retornamos
            if response.status_code == 200:
                json_response = response.json()
                try:
                    texto = json_response['candidates'][0]['content']['parts'][0]['text']
                    return texto
                except KeyError:
                    return "La IA respondió pero no generó texto (Bloqueo de seguridad)."
            
            # Si da error 404, probamos el siguiente modelo del bucle
            if response.status_code == 404:
                print(f"Modelo {modelo} no encontrado, probando siguiente...")
                continue
                
            # Si es otro error, lo reportamos
            return f"Error Google ({modelo}): {response.status_code} - {response.text}"

        except Exception as e:
            return f"Error de conexión: {str(e)}"

    return "❌ Error Crítico: Ningún modelo de Gemini respondió (Verifica tu API Key en Google AI Studio)."

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
    
    1. 🏛️ CALENDARIO OFICIAL:
    {ctx_db}
    
    2. 🌍 INTERNET:
    {ctx_web}
    
    3. 📄 PDF:
    {ctx_pdf}
    
    PREGUNTA: "{pregunta}"
    INSTRUCCIONES: Responde directo. Si es del ministerio usa la fuente 1. Si es general usa la 2.
    """
    
    # LLAMADA DIRECTA SIN LIBRERÍA
    respuesta_ia = consultar_gemini(prompt)
    return {"respuesta": respuesta_ia}