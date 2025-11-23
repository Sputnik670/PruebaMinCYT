import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import io
import requests
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import os
import pypdf
from duckduckgo_search import DDGS 

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
model = None
debug_log = [] # Guardamos el historial de intentos

def configurar_modelo():
    global debug_log
    debug_log = [] # Reset log
    
    if not GEMINI_API_KEY:
        debug_log.append("⚠️ API Key no encontrada en variables de entorno.")
        return None

    genai.configure(api_key=GEMINI_API_KEY)
    
    # Lista extendida con todas las variantes posibles de nombres
    candidatos = [
        'gemini-1.5-flash',
        'models/gemini-1.5-flash',
        'gemini-1.5-pro',
        'models/gemini-1.5-pro',
        'gemini-1.0-pro',
        'models/gemini-1.0-pro',
        'gemini-pro',
        'models/gemini-pro'
    ]

    print("🔄 Iniciando prueba exhaustiva V23...")

    for nombre in candidatos:
        try:
            print(f"🧪 Probando: {nombre}")
            # Configuramos sin safety settings estrictos para evitar bloqueos falsos en el test
            m = genai.GenerativeModel(nombre)
            m.generate_content("Test")
            print(f"✅ ¡CONECTADO! {nombre}")
            return m
        except Exception as e:
            error_msg = f"❌ {nombre}: {str(e)}"
            print(error_msg)
            debug_log.append(error_msg)
            continue
            
    return None

model = configurar_modelo()

# --- BÚSQUEDA WEB MANUAL ---
def buscar_en_web(consulta, max_results=3):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(consulta, max_results=max_results))
        if not results: return "Sin resultados web."
        texto = ""
        for i, r in enumerate(results):
            texto += f"WEB {i+1}: {r['title']} - {r['body']}\n"
        return texto
    except:
        return "Error en búsqueda web."

# --- ENLACES ---
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
    except:
        return None

@app.get("/")
def home():
    estado = "✅ Conectado" if model else "❌ Desconectado"
    return {"status": "online", "ia_status": estado}

@app.get("/api/dashboard")
def get_dashboard_data():
    # (Lógica Dashboard igual)
    df_bitacora = cargar_csv(URL_BITACORA)
    datos_bitacora = df_bitacora.to_dict(orient="records") if df_bitacora is not None else []
    df_ventas = cargar_csv(URL_VENTAS)
    datos_ventas_crudos = df_ventas.to_dict(orient="records") if df_ventas is not None else []
    datos_tendencia = []
    if df_ventas is not None:
        # ... (Lógica de tendencia igual)
        pass # Simplificado aquí para brevedad, mantener lógica original si se usa
    df_nueva = cargar_csv(URL_NUEVA)
    datos_nueva_tabla = df_nueva.to_dict(orient="records") if df_nueva is not None else []
    df_cal = cargar_csv(URL_CALENDARIO)
    datos_calendario = df_cal.to_dict(orient="records") if df_cal is not None else []

    return {
        "bitacora": datos_bitacora, "ventas_tabla": datos_ventas_crudos,
        "tendencia_grafico": [], "extra_tabla": datos_nueva_tabla, "calendario": datos_calendario
    }

@app.post("/api/chat")
async def chat_con_datos(pregunta: str = Form(...), file: UploadFile = File(None)):
    global model
    if not model:
        model = configurar_modelo()
        if not model:
            # AQUÍ ESTÁ LA CLAVE: Devolvemos el log de errores al usuario
            errores_str = "\n".join(debug_log[-3:]) # Mostramos los últimos 3 errores
            return {"respuesta": f"🛑 DIAGNÓSTICO DE ERROR:\nLa IA no pudo conectar. Aquí están los motivos técnicos:\n\n{errores_str}\n\nPor favor, verifica tu API Key."}

    df_ventas = cargar_csv(URL_VENTAS)
    df_extra = cargar_csv(URL_NUEVA)
    
    texto_pdf = ""
    if file:
        try:
            content = await file.read()
            reader = pypdf.PdfReader(io.BytesIO(content))
            for page in reader.pages: texto_pdf += page.extract_text()
        except: pass

    info_web = buscar_en_web(pregunta)

    contexto = f"""Eres un asistente experto.
    WEB: {info_web}
    DATOS:
    - Ventas: {df_ventas.tail(50).to_csv(index=False) if df_ventas is not None else 'N/A'}
    - Extra: {df_extra.to_csv(index=False) if df_extra is not None else 'N/A'}
    - PDF: {texto_pdf[:20000]}
    Pregunta: {pregunta}"""

    try:
        response = model.generate_content(contexto)
        return {"respuesta": response.text}
    except Exception as e:
        return {"respuesta": f"Error generando respuesta: {e}"}