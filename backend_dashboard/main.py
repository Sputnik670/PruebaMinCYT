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
from tabulate import tabulate # Importante para tablas bonitas

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

# --- CONFIGURACIÓN IA (GEMINI) ---
def configurar_modelo():
    if not GEMINI_API_KEY:
        print("⚠️ Falta GEMINI_API_KEY.")
        return None

    genai.configure(api_key=GEMINI_API_KEY)
    
    safety = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }

    candidatos = [
        'gemini-1.5-flash', 'models/gemini-1.5-flash',
        'gemini-1.5-pro', 'models/gemini-1.5-pro',
        'gemini-pro', 'models/gemini-pro'
    ]

    for nombre in candidatos:
        try:
            m = genai.GenerativeModel(nombre, safety_settings=safety)
            m.generate_content("Ping")
            print(f"✅ IA Conectada: {nombre}")
            return m
        except:
            continue
    return None

model = configurar_modelo()

# --- TAVILY ---
if TAVILY_API_KEY:
    try:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        print("✅ Tavily: ACTIVO")
    except: pass

def buscar_en_web(consulta):
    if not tavily_client: return "(Sin búsqueda web)"
    try:
        # search_depth="advanced" da mejores resultados para deportes/noticias
        resp = tavily_client.search(query=consulta, search_depth="advanced", max_results=5)
        txt = "--- RESULTADOS INTERNET (Ordenados por relevancia) ---\n"
        for r in resp.get('results', []):
            txt += f"* Título: {r.get('title')}\n  Info: {r.get('content')}\n  Fuente: {r.get('url')}\n\n"
        return txt
    except Exception as e: return f"(Error Web: {e})"

# --- CARGA DE DATOS ---
URL_BITACORA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv"
URL_VENTAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv"
# Esta es la que usas para el Calendario en el Frontend:
URL_CALENDARIO = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"

def cargar_csv(url, nombre="Datos"):
    try:
        if not url or "TU_LINK" in url: return None
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        df = pd.read_csv(io.BytesIO(r.content), encoding='utf-8').fillna("")
        return df
    except Exception:
        return None

@app.get("/api/dashboard")
def get_dashboard_data():
    # Endpoint para el Frontend (Gráficos y Tablas visuales)
    df_extra = cargar_csv(URL_CALENDARIO, "Calendario")
    return {
        "bitacora": cargar_csv(URL_BITACORA).to_dict(orient="records") if cargar_csv(URL_BITACORA) is not None else [],
        "ventas_tabla": cargar_csv(URL_VENTAS).to_dict(orient="records") if cargar_csv(URL_VENTAS) is not None else [],
        "extra_tabla": df_extra.to_dict(orient="records") if df_extra is not None else [],
        "tendencia_grafico": []
    }

@app.post("/api/chat")
async def chat_con_datos(pregunta: str = Form(...), file: UploadFile = File(None)):
    global model
    if not model: model = configurar_modelo()
    if not model: return {"respuesta": "❌ Error: IA no disponible."}

    # 1. Cargar TODAS las tablas para el Chat
    # Antes faltaba df_calendario, por eso no sabía qué responder
    df_ventas = cargar_csv(URL_VENTAS)
    df_bitacora = cargar_csv(URL_BITACORA)
    df_calendario = cargar_csv(URL_CALENDARIO)
    
    contexto_csv = ""
    
    # Agregamos Calendario al contexto (IMPORTANTE: Esto faltaba antes)
    if df_calendario is not None and not df_calendario.empty:
        contexto_csv += f"\n### 📅 CALENDARIO INTERNACIONAL / PROYECTOS (Tabla Completa):\n{df_calendario.to_markdown(index=False)}\n"
    
    if df_ventas is not None and not df_ventas.empty:
        contexto_csv += f"\n### 💰 VENTAS E INVERSIÓN (Últimos 20):\n{df_ventas.tail(20).to_markdown(index=False)}\n"
    
    if df_bitacora is not None and not df_bitacora.empty:
        contexto_csv += f"\n### ⏱️ BITÁCORA DE TAREAS (Primeros 20):\n{df_bitacora.head(20).to_markdown(index=False)}\n"

    # 2. PDF
    texto_pdf = ""
    if file:
        try:
            content = await file.read()
            pdf = pypdf.PdfReader(io.BytesIO(content))
            texto_pdf = "\n### 📄 CONTENIDO PDF ADJUNTO:\n"
            for p in pdf.pages[:7]: 
                texto_pdf += p.extract_text() + "\n"
        except: pass

    # 3. Web
    info_web = buscar_en_web(pregunta)

    # 4. Prompt Mejorado
    prompt = f"""
    Eres el Asistente de IA del MinCYT. Tienes acceso a 3 fuentes de verdad:

    FUENTE 1: DATOS INTERNOS (DASHBOARD)
    {contexto_csv}

    FUENTE 2: DOCUMENTO ADJUNTO (PDF)
    {texto_pdf}

    FUENTE 3: BÚSQUEDA EN INTERNET (Para actualidad y deportes)
    {info_web}

    PREGUNTA DEL USUARIO: "{pregunta}"

    INSTRUCCIONES MAESTRAS:
    1. **Prioridad Interna:** Si preguntan por "Calendario", "Proyectos", "Ventas" o "Bitácora", BUSCA EN LA FUENTE 1. Si la fecha solicitada está en la tabla, responde con ese dato exacto.
    2. **Prioridad Externa:** Si preguntan por deportes (ej. Boca, River) o noticias, confía en la FUENTE 3. Si hay resultados conflictivos, usa el más reciente. Sé directo (ej: "Boca juega hoy contra X").
    3. **Formato:** Responde en español, sé conciso y profesional.
    """

    try:
        res = model.generate_content(prompt)
        return {"respuesta": res.text}
    except Exception as e:
        return {"respuesta": f"Error IA: {e}"}