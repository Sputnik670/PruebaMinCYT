import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import io
import requests
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import os
import pypdf
from tavily import TavilyClient # El buscador profesional

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
        print("⚠️ Falta GEMINI_API_KEY")
        return None

    genai.configure(api_key=GEMINI_API_KEY)
    
    safety = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }

    # Intentamos conectar con el mejor modelo disponible
    candidatos = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.0-pro', 'gemini-pro']
    
    for nombre in candidatos:
        try:
            print(f"🧪 Probando IA: {nombre}")
            m = genai.GenerativeModel(nombre, safety_settings=safety)
            m.generate_content("Test")
            print(f"✅ IA Conectada: {nombre}")
            return m
        except:
            continue
            
    return None

model = configurar_modelo()

# --- CONFIGURACIÓN BÚSQUEDA (TAVILY) ---
if TAVILY_API_KEY:
    try:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        print("✅ Buscador Tavily: ACTIVO")
    except Exception as e:
        print(f"❌ Error Tavily: {e}")

def buscar_en_web(consulta):
    if not tavily_client:
        return "AVISO: No hay conexión a internet (Falta TAVILY_API_KEY)."
    
    try:
        print(f"🌍 Buscando en Tavily: {consulta}")
        # Tavily nos da respuestas optimizadas para IA
        response = tavily_client.search(query=consulta, search_depth="basic", max_results=3)
        
        texto = "RESULTADOS DE INTERNET (TAVILY):\n"
        for r in response['results']:
            texto += f"- {r['title']}: {r['content']} (Fuente: {r['url']})\n"
        return texto
    except Exception as e:
        print(f"⚠️ Error búsqueda: {e}")
        return f"Error al buscar en internet: {e}"

# --- ENLACES DE DATOS ---
URL_BITACORA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv"
URL_VENTAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv"
URL_NUEVA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"
URL_CALENDARIO = "TU_LINK_CALENDARIO_AQUI" 

def cargar_csv(url):
    try:
        if "TU_LINK" in url: return None
        response = requests.get(url)
        df = pd.read_csv(io.BytesIO(response.content), encoding='utf-8')
        df = df.fillna("")
        return df
    except: return None

@app.get("/")
def home():
    estado_web = "✅ Activo" if tavily_client else "❌ Inactivo"
    return {"status": "online", "internet": estado_web}

@app.get("/api/dashboard")
def get_dashboard_data():
    # (Lógica Dashboard intacta)
    df_bitacora = cargar_csv(URL_BITACORA)
    datos_bitacora = df_bitacora.to_dict(orient="records") if df_bitacora is not None else []
    df_ventas = cargar_csv(URL_VENTAS)
    datos_ventas_crudos = df_ventas.to_dict(orient="records") if df_ventas is not None else []
    datos_tendencia = [] # Simplificado
    df_nueva = cargar_csv(URL_NUEVA)
    datos_nueva_tabla = df_nueva.to_dict(orient="records") if df_nueva is not None else []
    df_cal = cargar_csv(URL_CALENDARIO)
    datos_calendario = df_cal.to_dict(orient="records") if df_cal is not None else []

    return {
        "bitacora": datos_bitacora, "ventas_tabla": datos_ventas_crudos,
        "tendencia_grafico": datos_tendencia, "extra_tabla": datos_nueva_tabla, "calendario": datos_calendario
    }

@app.post("/api/chat")
async def chat_con_datos(
    pregunta: str = Form(...), 
    file: UploadFile = File(None)
):
    global model
    if not model:
        model = configurar_modelo()
        if not model: return {"respuesta": "❌ Error IA: No disponible."}

    # 1. Datos Internos
    df_ventas = cargar_csv(URL_VENTAS)
    df_extra = cargar_csv(URL_NUEVA)
    
    # 2. PDF Adjunto
    texto_pdf = ""
    if file:
        try:
            content = await file.read()
            reader = pypdf.PdfReader(io.BytesIO(content))
            for page in reader.pages: texto_pdf += page.extract_text()
        except: pass

    # 3. Búsqueda Web (Tavily)
    info_web = buscar_en_web(pregunta)

    # 4. Contexto Maestro
    contexto = f"""Eres un asistente experto del MinCYT.
    
    INFORMACIÓN DE INTERNET (Actualidad):
    {info_web}
    
    DATOS INTERNOS (CSV):
    -- Ventas: {df_ventas.tail(50).to_csv(index=False) if df_ventas is not None else 'N/A'}
    -- Extra: {df_extra.to_csv(index=False) if df_extra is not None else 'N/A'}
    
    DOCUMENTO PDF:
    {texto_pdf[:20000]}
    
    PREGUNTA: {pregunta}
    
    INSTRUCCIONES:
    - Usa la INFORMACIÓN DE INTERNET si la pregunta requiere datos actuales o externos (ej: valor bitcoin, noticias).
    - Usa los DATOS INTERNOS si la pregunta es sobre gestión del ministerio.
    - Si Tavily trajo resultados, cítalos.
    """

    try:
        response = model.generate_content(contexto)
        return {"respuesta": response.text}
    except Exception as e:
        return {"respuesta": f"Error IA: {e}"}