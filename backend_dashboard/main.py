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

# --- INICIALIZACIÓN APP ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURACIÓN Y VARIABLES ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")

# URLs de Google Sheets (Publicados como CSV)
URLS = {
    "VENTAS": "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv",
    "BITACORA": "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv",
    "CALENDARIO": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"
}

# --- MÓDULO 1: GESTIÓN DE IA (GEMINI) ---
def obtener_modelo_gemini():
    """Configura y devuelve el mejor modelo disponible dinámicamente."""
    if not GEMINI_API_KEY:
        print("⚠️ Error: Falta GEMINI_API_KEY")
        return None

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Configuramos seguridad para que no bloquee documentos técnicos
        safety = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }

        # Lista de candidatos preferidos
        candidatos = [
            'gemini-1.5-flash', 
            'models/gemini-1.5-flash',
            'gemini-1.5-pro',
            'gemini-1.0-pro',
            'gemini-pro'
        ]

        # Intentamos conectar con el primero que funcione
        for nombre in candidatos:
            try:
                model = genai.GenerativeModel(nombre, safety_settings=safety)
                return model
            except:
                continue
        
        print("❌ No se pudo conectar con ningún modelo Gemini conocido.")
        return None
    except Exception as e:
        print(f"💀 Error fatal configurando Gemini: {e}")
        return None

# Instancia global del modelo
model = obtener_modelo_gemini()

# --- MÓDULO 2: GESTIÓN DE DATOS (DASHBOARD) ---
def descargar_csv(url):
    """Descarga un CSV y devuelve un DataFrame de Pandas."""
    try:
        if not url or "TU_LINK" in url: return None
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return pd.read_csv(io.BytesIO(response.content), encoding='utf-8').fillna("")
    except Exception as e:
        print(f"⚠️ Error descargando CSV: {e}")
        return None

def obtener_contexto_dashboard():
    """Recopila toda la data del dashboard y la formatea como texto Markdown."""
    texto = ""
    
    # 1. Calendario
    df_cal = descargar_csv(URLS["CALENDARIO"])
    if df_cal is not None and not df_cal.empty:
        texto += f"\n### 📅 CALENDARIO Y PROYECTOS:\n{df_cal.to_markdown(index=False)}\n"
    
    # 2. Ventas (Últimos 20 registros para no saturar)
    df_ventas = descargar_csv(URLS["VENTAS"])
    if df_ventas is not None and not df_ventas.empty:
        texto += f"\n### 💰 VENTAS RECIENTES:\n{df_ventas.tail(20).to_markdown(index=False)}\n"
        
    # 3. Bitácora (Primeros 20 registros)
    df_bit = descargar_csv(URLS["BITACORA"])
    if df_bit is not None and not df_bit.empty:
        texto += f"\n### ⏱️ BITÁCORA DE TAREAS:\n{df_bit.head(20).to_markdown(index=False)}\n"
        
    if not texto:
        texto = "(No hay datos del dashboard disponibles actualmente)"
        
    return texto

# --- MÓDULO 3: GESTIÓN DE PDF ---
async def obtener_contexto_pdf(file: UploadFile):
    """Lee un archivo PDF y extrae su texto."""
    if not file: return ""
    
    texto = ""
    try:
        content = await file.read()
        pdf_reader = pypdf.PdfReader(io.BytesIO(content))
        texto += f"\n### 📄 CONTENIDO DEL ARCHIVO ADJUNTO ({file.filename}):\n"
        # Leemos hasta 10 páginas para no exceder límites
        for i, page in enumerate(pdf_reader.pages[:10]):
            texto += page.extract_text() + "\n"
    except Exception as e:
        texto += f"\n(Error leyendo el PDF: {e})\n"
    return texto

# --- MÓDULO 4: GESTIÓN WEB (TAVILY) ---
def obtener_contexto_web(consulta):
    """Busca en internet si es necesario."""
    if not TAVILY_API_KEY: return "(Búsqueda web desactivada)"
    
    try:
        tavily = TavilyClient(api_key=TAVILY_API_KEY)
        # 'advanced' es mejor para noticias y hechos recientes
        resp = tavily.search(query=consulta, search_depth="advanced", max_results=4)
        
        texto = "\n### 🌍 RESULTADOS DE BÚSQUEDA WEB:\n"
        for r in resp.get('results', []):
            texto += f"- **{r.get('title')}**: {r.get('content')} [Fuente: {r.get('url')}]\n"
        return texto
    except Exception as e:
        return f"(Error en búsqueda web: {e})"

# --- ENDPOINTS ---

@app.get("/api/dashboard")
def get_dashboard_data():
    """Endpoint exclusivo para los gráficos del Frontend."""
    df_cal = descargar_csv(URLS["CALENDARIO"])
    df_ventas = descargar_csv(URLS["VENTAS"])
    df_bit = descargar_csv(URLS["BITACORA"])
    
    return {
        "bitacora": df_bit.to_dict(orient="records") if df_bit is not None else [],
        "ventas_tabla": df_ventas.to_dict(orient="records") if df_ventas is not None else [],
        "extra_tabla": df_cal.to_dict(orient="records") if df_cal is not None else [],
        "tendencia_grafico": [] # Aquí iría lógica extra si la necesitas
    }

@app.post("/api/chat")
async def chat_endpoint(pregunta: str = Form(...), file: UploadFile = File(None)):
    """Orquestador principal del Chatbot."""
    global model
    
    # 1. Asegurar modelo
    if not model:
        model = obtener_modelo_gemini()
        if not model:
            return {"respuesta": "❌ Error Crítico: No se pudo conectar con la IA. Verifica las claves API en el servidor."}

    # 2. Recopilar Contextos (Los 3 Pilares)
    contexto_dashboard = obtener_contexto_dashboard()
    contexto_pdf = await obtener_contexto_pdf(file)
    contexto_web = obtener_contexto_web(pregunta)

    # 3. Construir el Prompt Maestro (Jerarquía Lógica)
    prompt = f"""
    Eres el Asistente Inteligente del MinCYT. Tu objetivo es responder con precisión basándote en la siguiente jerarquía de fuentes:

    --- FUENTE 1: DATOS INTERNOS (DASHBOARD) ---
    (Prioridad MÁXIMA. Úsalo para preguntas sobre ventas, proyectos, fechas internas o tareas)
    {contexto_dashboard}

    --- FUENTE 2: DOCUMENTO ADJUNTO ---
    (Prioridad ALTA si el usuario pregunta sobre "este archivo" o "el documento")
    {contexto_pdf}

    --- FUENTE 3: INFORMACIÓN DE INTERNET ---
    (Úsalo SOLO si la respuesta no está en el Dashboard ni en el PDF. Ideal para deportes, noticias o conceptos generales)
    {contexto_web}

    --- PREGUNTA DEL USUARIO ---
    "{pregunta}"

    INSTRUCCIONES DE RESPUESTA:
    1. Analiza primero el Dashboard. Si el dato está ahí, responde con eso.
    2. Si no, busca en el PDF.
    3. Si no, usa la información de Internet.
    4. Cita la fuente de tu respuesta (ej: "Según la base de datos interna...", "Según noticias recientes...").
    5. Sé breve y profesional.
    """

    # 4. Generar Respuesta
    try:
        response = model.generate_content(prompt)
        return {"respuesta": response.text}
    except Exception as e:
        return {"respuesta": f"❌ Ocurrió un error generando la respuesta: {str(e)}"}