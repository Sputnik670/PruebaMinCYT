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

    print("🔍 Buscando modelos Gemini disponibles...")
    modelos_disponibles = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                modelos_disponibles.append(m.name)
    except Exception as e:
        print(f"⚠️ Error listando modelos: {e}")

    # Prioridad de modelos
    candidatos = [
        'gemini-1.5-flash', 'models/gemini-1.5-flash',
        'gemini-1.5-pro', 'models/gemini-1.5-pro',
        'gemini-pro', 'models/gemini-pro'
    ]

    # Si encontramos flash en la lista oficial, lo ponemos primero
    for m in modelos_disponibles:
        if 'flash' in m: candidatos.insert(0, m)

    for nombre in candidatos:
        try:
            m = genai.GenerativeModel(nombre, safety_settings=safety)
            m.generate_content("Ping")
            print(f"✅ IA Conectada: {nombre}")
            return m
        except:
            continue
            
    print("❌ Error crítico: No se pudo conectar ninguna IA.")
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
        resp = tavily_client.search(query=consulta, search_depth="basic", max_results=3)
        txt = "--- INTERNET ---\n"
        for r in resp.get('results', []):
            txt += f"* {r.get('title')}: {r.get('content')} ({r.get('url')})\n"
        return txt
    except Exception as e: return f"(Error Web: {e})"

# --- CARGA DE DATOS ---
URL_BITACORA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv"
URL_VENTAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv"
URL_NUEVA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"
URL_CALENDARIO = "TU_LINK_CALENDARIO"

def cargar_csv(url, nombre="Datos"):
    try:
        if not url or "TU_LINK" in url: return None
        r = requests.get(url, timeout=10) # Timeout para no colgar
        r.raise_for_status()
        df = pd.read_csv(io.BytesIO(r.content), encoding='utf-8').fillna("")
        print(f"📊 {nombre}: Cargadas {len(df)} filas.")
        return df
    except Exception as e:
        print(f"⚠️ Error cargando {nombre}: {e}")
        return None

@app.get("/api/dashboard")
def get_dashboard_data():
    return {
        "bitacora": cargar_csv(URL_BITACORA, "Bitácora").to_dict(orient="records") if cargar_csv(URL_BITACORA) is not None else [],
        "ventas_tabla": cargar_csv(URL_VENTAS, "Ventas").to_dict(orient="records") if cargar_csv(URL_VENTAS) is not None else [],
        "extra_tabla": cargar_csv(URL_NUEVA, "Extra").to_dict(orient="records") if cargar_csv(URL_NUEVA) is not None else [],
        "calendario": [],
        "tendencia_grafico": []
    }

@app.post("/api/chat")
async def chat_con_datos(pregunta: str = Form(...), file: UploadFile = File(None)):
    global model
    if not model: model = configurar_modelo()
    if not model: return {"respuesta": "❌ Error de conexión con la IA."}

    # 1. Cargar Datos CSV (Optimizados para IA)
    df_ventas = cargar_csv(URL_VENTAS, "Ventas Chat")
    df_bitacora = cargar_csv(URL_BITACORA, "Bitácora Chat")
    
    contexto_csv = ""
    if df_ventas is not None and not df_ventas.empty:
        # Usamos to_markdown que la IA entiende mejor
        contexto_csv += f"\n### VENTAS (Últimos 30 registros):\n{df_ventas.tail(30).to_markdown(index=False)}\n"
    
    if df_bitacora is not None and not df_bitacora.empty:
        contexto_csv += f"\n### BITÁCORA DE TAREAS (Primeros 20 registros):\n{df_bitacora.head(20).to_markdown(index=False)}\n"

    if not contexto_csv:
        contexto_csv = "(No se pudieron cargar los datos del Dashboard. Revisa los links de Google Sheets)"

    # 2. PDF
    texto_pdf = ""
    if file:
        try:
            content = await file.read()
            pdf = pypdf.PdfReader(io.BytesIO(content))
            texto_pdf = "\n### CONTENIDO PDF ADJUNTO:\n"
            for p in pdf.pages[:5]: # Limitamos a 5 pags iniciales por velocidad
                texto_pdf += p.extract_text() + "\n"
        except: pass

    # 3. Web
    info_web = buscar_en_web(pregunta)

    # 4. Prompt
    prompt = f"""
    Actúa como un Analista de Datos del MinCYT. Tienes acceso a tres fuentes:
    
    1. **DATOS INTERNOS (DASHBOARD)**:
    {contexto_csv}
    
    2. **DOCUMENTO ADJUNTO**:
    {texto_pdf}
    
    3. **INTERNET**:
    {info_web}
    
    PREGUNTA DEL USUARIO: "{pregunta}"
    
    Responde de forma clara. Si usas datos de la tabla, sé específico (ej: "Hay X ventas...").
    """

    try:
        res = model.generate_content(prompt)
        return {"respuesta": res.text}
    except Exception as e:
        return {"respuesta": f"Error generando respuesta: {e}"}