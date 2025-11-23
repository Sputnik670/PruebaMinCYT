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
from tabulate import tabulate # Librería para tablas markdown

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

model = None
tavily_client = None

# --- CONFIGURACIÓN IA (GEMINI - VERSIÓN ROBUSTA) ---
def configurar_modelo():
    if not GEMINI_API_KEY:
        print("⚠️ Error Crítico: Falta GEMINI_API_KEY.")
        return None

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        safety = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }

        # 1. Diagnóstico: Listar qué ve la API realmente
        print("🔍 Iniciando conexión con IA...")
        candidatos = [
            'gemini-1.5-flash',
            'gemini-1.5-pro',
            'gemini-1.0-pro',
            'gemini-pro'
        ]

        # Intento de conexión iterativo
        for nombre in candidatos:
            try:
                print(f"🧪 Probando modelo: {nombre}...")
                m = genai.GenerativeModel(nombre, safety_settings=safety)
                # Prueba de fuego: Generar un token
                m.generate_content("Ping")
                print(f"✅ IA Conectada exitosamente con: {nombre}")
                return m
            except Exception as e:
                print(f"   ❌ Falló {nombre}: {e}")
                continue
        
        print("💀 Fallaron todos los intentos de conexión con Gemini.")
        return None

    except Exception as e:
        print(f"⚠️ Error fatal configurando IA: {e}")
        return None

# Inicializamos el modelo
model = configurar_modelo()

# --- TAVILY ---
if TAVILY_API_KEY:
    try:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        print("✅ Tavily: ACTIVO")
    except Exception as e:
        print(f"❌ Error Tavily: {e}")

def buscar_en_web(consulta):
    if not tavily_client: return "(Sin búsqueda web - Falta Key)"
    try:
        resp = tavily_client.search(query=consulta, search_depth="advanced", max_results=5)
        txt = "--- RESULTADOS INTERNET ---\n"
        for r in resp.get('results', []):
            txt += f"* {r.get('title')}: {r.get('content')} ({r.get('url')})\n\n"
        return txt
    except Exception as e: return f"(Error Búsqueda: {e})"

# --- CARGA DE DATOS ---
URL_BITACORA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv"
URL_VENTAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv"
URL_CALENDARIO = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"

def cargar_csv(url):
    try:
        if not url or "TU_LINK" in url: return None
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        df = pd.read_csv(io.BytesIO(r.content), encoding='utf-8').fillna("")
        return df
    except Exception as e:
        print(f"⚠️ Error cargando CSV: {e}")
        return None

@app.get("/api/dashboard")
def get_dashboard_data():
    df_extra = cargar_csv(URL_CALENDARIO)
    return {
        "bitacora": cargar_csv(URL_BITACORA).to_dict(orient="records") if cargar_csv(URL_BITACORA) is not None else [],
        "ventas_tabla": cargar_csv(URL_VENTAS).to_dict(orient="records") if cargar_csv(URL_VENTAS) is not None else [],
        "extra_tabla": df_extra.to_dict(orient="records") if df_extra is not None else [],
        "tendencia_grafico": []
    }

@app.post("/api/chat")
async def chat_con_datos(pregunta: str = Form(...), file: UploadFile = File(None)):
    global model
    # Reintento de conexión si se cayó
    if not model: 
        print("🔄 Reintentando conexión con IA...")
        model = configurar_modelo()
    
    if not model: 
        return {"respuesta": "❌ Error Crítico: El sistema no puede conectar con la IA de Google. Por favor revisa los logs del servidor."}

    # 1. Contexto CSV
    df_ventas = cargar_csv(URL_VENTAS)
    df_bitacora = cargar_csv(URL_BITACORA)
    df_calendario = cargar_csv(URL_CALENDARIO)
    
    contexto_csv = ""
    try:
        if df_calendario is not None and not df_calendario.empty:
            contexto_csv += f"\n### 📅 CALENDARIO / PROYECTOS:\n{df_calendario.to_markdown(index=False)}\n"
        if df_ventas is not None and not df_ventas.empty:
            contexto_csv += f"\n### 💰 VENTAS:\n{df_ventas.tail(20).to_markdown(index=False)}\n"
        if df_bitacora is not None and not df_bitacora.empty:
            contexto_csv += f"\n### ⏱️ BITÁCORA:\n{df_bitacora.head(20).to_markdown(index=False)}\n"
    except Exception as e:
        print(f"Error formateando tablas: {e}")
        contexto_csv += "\n(Error al procesar las tablas de datos)\n"

    # 2. PDF
    texto_pdf = ""
    if file:
        try:
            content = await file.read()
            pdf = pypdf.PdfReader(io.BytesIO(content))
            texto_pdf = "\n### 📄 PDF ADJUNTO:\n"
            for p in pdf.pages[:10]: 
                texto_pdf += p.extract_text() + "\n"
        except: pass

    # 3. Web
    info_web = buscar_en_web(pregunta)

    # 4. Prompt
    prompt = f"""
    Eres el Asistente MinCYT. Fuentes:
    
    1. [INTERNO] TABLAS DE DATOS:
    {contexto_csv}
    
    2. [ARCHIVO] PDF ADJUNTO:
    {texto_pdf}
    
    3. [EXTERNO] INTERNET:
    {info_web}
    
    CONSULTA: "{pregunta}"
    
    INSTRUCCIONES:
    - Busca primero en [INTERNO] para fechas, proyectos y ventas.
    - Usa [EXTERNO] solo para noticias o deportes.
    - Responde directo y conciso.
    """

    try:
        res = model.generate_content(prompt)
        return {"respuesta": res.text}
    except Exception as e:
        return {"respuesta": f"Error generando respuesta: {e}"}