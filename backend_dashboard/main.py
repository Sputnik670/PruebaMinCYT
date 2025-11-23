import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import io
import requests
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import os
import pypdf
from tavily import TavilyClient
import sys
import time  # <--- NUEVO: Para medir el tiempo del caché

# --- INICIALIZACIÓN APP ---
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

URLS = {
    "VENTAS": "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv",
    "BITACORA": "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv",
    "CALENDARIO": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"
}

# --- SISTEMA DE CACHÉ (NUEVO) ---
# Guardaremos los datos aquí para no descargarlos en cada click
CACHE_DATOS = {
    "dashboard_texto": "",
    "ultimo_update": 0
}
TIEMPO_CACHE_SEGUNDOS = 300  # 5 Minutos de memoria (ajustable)

# --- IA ---
def obtener_modelo_gemini():
    if not GEMINI_API_KEY: return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        safety = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }
        # Lista simplificada para conexión rápida
        candidatos = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
        for nombre in candidatos:
            try:
                return genai.GenerativeModel(nombre, safety_settings=safety)
            except: continue
        return None
    except: return None

model = obtener_modelo_gemini()

# --- DATOS ---
def descargar_csv(url):
    try:
        if not url or "TU_LINK" in url: return None
        # Timeout corto (3s) para no bloquear si Google tarda
        r = requests.get(url, timeout=3) 
        r.raise_for_status()
        return pd.read_csv(io.BytesIO(r.content), encoding='utf-8').fillna("")
    except: return None

def obtener_contexto_dashboard_optimizado():
    """Descarga datos SOLO si pasaron más de 5 minutos o está vacío."""
    global CACHE_DATOS
    ahora = time.time()
    
    # Si tenemos datos y son frescos (menos de 5 min), úsalos.
    if CACHE_DATOS["dashboard_texto"] and (ahora - CACHE_DATOS["ultimo_update"] < TIEMPO_CACHE_SEGUNDOS):
        print("⚡ Usando datos de CACHÉ (Rápido)")
        return CACHE_DATOS["dashboard_texto"]

    print("🐢 Descargando datos nuevos de Google Sheets...")
    texto = ""
    
    # Descargas
    df_cal = descargar_csv(URLS["CALENDARIO"])
    df_ventas = descargar_csv(URLS["VENTAS"])
    df_bit = descargar_csv(URLS["BITACORA"])
    
    # Formateo
    if df_cal is not None and not df_cal.empty:
        texto += f"\n### 📅 CALENDARIO Y PROYECTOS:\n{df_cal.to_markdown(index=False)}\n"
    if df_ventas is not None and not df_ventas.empty:
        texto += f"\n### 💰 VENTAS RECIENTES:\n{df_ventas.tail(20).to_markdown(index=False)}\n"
    if df_bit is not None and not df_bit.empty:
        texto += f"\n### ⏱️ BITÁCORA DE TAREAS:\n{df_bit.head(20).to_markdown(index=False)}\n"

    if not texto: texto = "(Datos no disponibles)"

    # Actualizar Caché
    CACHE_DATOS["dashboard_texto"] = texto
    CACHE_DATOS["ultimo_update"] = ahora
    return texto

# --- PDF & WEB ---
async def obtener_contexto_pdf(file: UploadFile):
    if not file: return ""
    try:
        content = await file.read()
        pdf = pypdf.PdfReader(io.BytesIO(content))
        txt = f"\n### 📄 PDF ({file.filename}):\n"
        for p in pdf.pages[:5]: txt += p.extract_text() + "\n" # Solo 5 pags para velocidad
        return txt
    except: return ""

def obtener_contexto_web(consulta):
    if not TAVILY_API_KEY: return ""
    try:
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        # Search depth basic es 3x más rápido que advanced
        resp = tavily.search(query=consulta, search_depth="basic", max_results=3)
        txt = "\n### 🌍 INTERNET:\n"
        for r in resp.get('results', []): txt += f"- {r.get('title')}: {r.get('content')}\n"
        return txt
    except: return ""

# --- ENDPOINTS ---
@app.get("/api/dashboard")
def get_dashboard_data():
    # Este endpoint sigue descargando en vivo para que los gráficos sean realtime
    return {
        "bitacora": descargar_csv(URLS["BITACORA"]).to_dict(orient="records") if descargar_csv(URLS["BITACORA"]) is not None else [],
        "ventas_tabla": descargar_csv(URLS["VENTAS"]).to_dict(orient="records") if descargar_csv(URLS["VENTAS"]) is not None else [],
        "extra_tabla": descargar_csv(URLS["CALENDARIO"]).to_dict(orient="records") if descargar_csv(URLS["CALENDARIO"]) is not None else [],
        "tendencia_grafico": []
    }

@app.post("/api/chat")
async def chat_endpoint(pregunta: str = Form(...), file: UploadFile = File(None)):
    global model
    if not model: model = obtener_modelo_gemini()
    if not model: return {"respuesta": "Error de conexión IA."}

    # Usamos la función optimizada con caché
    contexto_dash = obtener_contexto_dashboard_optimizado()
    contexto_pdf = await obtener_contexto_pdf(file)
    
    # Solo buscamos en web si la pregunta parece requerirlo (palabras clave) para ahorrar tiempo
    # O buscamos siempre pero con modo "basic" (ya configurado arriba)
    contexto_web = obtener_contexto_web(pregunta)

    prompt = f"""
    Eres el Asistente MinCYT. Responde rápido y conciso.
    
    FUENTES:
    1. DASHBOARD (Interno):
    {contexto_dash}
    
    2. PDF:
    {contexto_pdf}
    
    3. INTERNET:
    {contexto_web}
    
    PREGUNTA: "{pregunta}"
    """

    try:
        res = model.generate_content(prompt)
        return {"respuesta": res.text}
    except Exception as e:
        return {"respuesta": f"Error: {str(e)}"}