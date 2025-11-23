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
from tabulate import tabulate
import sys

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

# --- CONFIGURACIÓN IA (ENFOQUE DINÁMICO) ---
def configurar_modelo():
    print(f"📦 VERSIÓN DE PYTHON: {sys.version}")
    try:
        print(f"📦 VERSIÓN DE GOOGLE-GENAI: {genai.__version__}")
    except:
        print("📦 VERSIÓN DE GOOGLE-GENAI: (No se pudo determinar)")

    if not GEMINI_API_KEY:
        print("⚠️ Error: Falta GEMINI_API_KEY.")
        return None

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Configuración de seguridad
        safety = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }

        print("🔍 PREGUNTANDO A GOOGLE QUÉ MODELOS TENEMOS DISPONIBLES...")
        
        modelo_elegido = None
        
        # 1. Listar modelos reales disponibles para tu API Key
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    nombre = m.name
                    print(f"   - Disponible: {nombre}")
                    
                    # Prioridad: Flash > Pro 1.5 > Pro 1.0
                    if 'flash' in nombre and '1.5' in nombre:
                        modelo_elegido = nombre
                    elif 'pro' in nombre and '1.5' in nombre and not modelo_elegido:
                        modelo_elegido = nombre
                    elif 'gemini-pro' in nombre and not modelo_elegido:
                        modelo_elegido = nombre
        except Exception as e:
            print(f"⚠️ Error listando modelos (Posible error de API Key o Región): {e}")

        # 2. Si no encontramos nada en la lista (raro), probamos el fallback
        if not modelo_elegido:
            print("⚠️ No se encontró modelo preferido en la lista. Usando 'gemini-1.5-flash' a ciegas.")
            modelo_elegido = 'gemini-1.5-flash'
        
        print(f"🎯 INTENTANDO CONECTAR CON: {modelo_elegido}")
        
        try:
            m = genai.GenerativeModel(modelo_elegido, safety_settings=safety)
            response = m.generate_content("Hola")
            print(f"✅ ¡CONEXIÓN EXITOSA CON {modelo_elegido}!")
            return m
        except Exception as e:
            print(f"❌ Falló la conexión final con {modelo_elegido}: {e}")
            return None

    except Exception as e:
        print(f"💀 Error fatal en configuración: {e}")
        return None

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
    if not model: 
        print("🔄 Reintentando conexión con IA...")
        model = configurar_modelo()
    
    if not model: 
        return {"respuesta": "❌ Error Crítico: No hay conexión con Gemini. Revisa los logs en Render."}

    # Contexto
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
    except:
        contexto_csv += "\n(Datos internos no disponibles)\n"

    texto_pdf = ""
    if file:
        try:
            content = await file.read()
            pdf = pypdf.PdfReader(io.BytesIO(content))
            texto_pdf = "\n### 📄 PDF ADJUNTO:\n"
            for p in pdf.pages[:10]: texto_pdf += p.extract_text() + "\n"
        except: pass

    info_web = buscar_en_web(pregunta)

    prompt = f"""
    Eres el Asistente Inteligente del MinCYT.
    
    FUENTES DE INFORMACIÓN:
    1. [INTERNO] DASHBOARD (Prioridad ALTA para datos del ministerio):
    {contexto_csv}
    
    2. [ARCHIVO] PDF (Prioridad ALTA si el usuario pregunta por el archivo):
    {texto_pdf}
    
    3. [WEB] INTERNET (Prioridad ALTA para actualidad y deportes):
    {info_web}
    
    PREGUNTA: "{pregunta}"
    """

    try:
        res = model.generate_content(prompt)
        return {"respuesta": res.text}
    except Exception as e:
        return {"respuesta": f"Error generando respuesta: {e}"}