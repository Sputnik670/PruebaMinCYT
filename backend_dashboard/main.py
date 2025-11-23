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

# --- CONFIGURACIÓN IA ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
model = None

def configurar_modelo():
    if not GEMINI_API_KEY:
        print("⚠️ Sin API Key")
        return None

    genai.configure(api_key=GEMINI_API_KEY)
    safety = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }

    try:
        # Intentamos Flash primero (rápido y bueno para contexto largo)
        return genai.GenerativeModel('gemini-1.5-flash', safety_settings=safety)
    except:
        # Fallback a Pro
        return genai.GenerativeModel('gemini-pro', safety_settings=safety)

model = configurar_modelo()

# --- BÚSQUEDA WEB MANUAL (DuckDuckGo) ---
def buscar_en_web(consulta, max_results=3):
    try:
        print(f"🌍 Buscando en internet: {consulta}")
        with DDGS() as ddgs:
            results = list(ddgs.text(consulta, max_results=max_results))
            
        if not results:
            return "No se encontraron resultados relevantes en la web."
            
        texto_busqueda = ""
        for i, r in enumerate(results):
            texto_busqueda += f"RESULTADO {i+1}:\nTitulo: {r['title']}\nResumen: {r['body']}\nFuente: {r['href']}\n\n"
            
        return texto_busqueda
    except Exception as e:
        print(f"⚠️ Error en búsqueda web: {e}")
        return "No se pudo realizar la búsqueda web en este momento."

# --- TUS ENLACES ---
URL_BITACORA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv"
URL_VENTAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv"
URL_NUEVA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"
URL_CALENDARIO = "TU_LINK_CALENDARIO_AQUI" 

# --- HERRAMIENTAS ---
def limpiar_dinero(valor):
    if pd.isna(valor): return 0.0
    s = str(valor).replace("$", "").replace(" ", "").strip()
    if "," in s: s = s.replace(".", "").replace(",", ".")
    return float(s) if s else 0.0

def cargar_csv(url):
    try:
        if "TU_LINK" in url: return None
        response = requests.get(url)
        response.raise_for_status()
        df = pd.read_csv(io.BytesIO(response.content), encoding='utf-8')
        df = df.fillna("")
        return df
    except Exception:
        return None

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Backend V21 - Full Power"}

@app.get("/api/dashboard")
def get_dashboard_data():
    # (Lógica Dashboard igual)
    df_bitacora = cargar_csv(URL_BITACORA)
    datos_bitacora = df_bitacora.to_dict(orient="records") if df_bitacora is not None else []

    df_ventas = cargar_csv(URL_VENTAS)
    datos_tendencia = []
    datos_ventas_crudos = []

    if df_ventas is not None:
        datos_ventas_crudos = df_ventas.to_dict(orient="records")
        col_dinero = next((c for c in df_ventas.columns if "Invers" in c or "Venta" in c), None)
        col_fecha = next((c for c in df_ventas.columns if "Fecha" in c), None)

        if col_dinero and col_fecha:
            df_ventas['MontoLimpio'] = df_ventas[col_dinero].apply(limpiar_dinero)
            df_ventas['FechaDt'] = pd.to_datetime(df_ventas[col_fecha], dayfirst=True, errors='coerce')
            df_ventas.dropna(subset=['FechaDt'], inplace=True)
            agrupado = df_ventas.groupby(df_ventas['FechaDt'].dt.to_period('M'))['MontoLimpio'].sum().reset_index()
            agrupado['FechaStr'] = agrupado['FechaDt'].astype(str)
            datos_tendencia = agrupado[['FechaStr', 'MontoLimpio']].rename(
                columns={'FechaStr': 'fecha', 'MontoLimpio': 'monto'}
            ).to_dict(orient="records")

    df_nueva = cargar_csv(URL_NUEVA)
    datos_nueva_tabla = df_nueva.to_dict(orient="records") if df_nueva is not None else []
    
    df_cal = cargar_csv(URL_CALENDARIO)
    datos_calendario = df_cal.to_dict(orient="records") if df_cal is not None else []

    return {
        "bitacora": datos_bitacora,
        "ventas_tabla": datos_ventas_crudos,
        "tendencia_grafico": datos_tendencia,
        "extra_tabla": datos_nueva_tabla,
        "calendario": datos_calendario
    }

@app.post("/api/chat")
async def chat_con_datos(
    pregunta: str = Form(...), 
    file: UploadFile = File(None)
):
    global model
    if not model:
        model = configurar_modelo()
        if not model:
            return {"respuesta": "❌ Error IA: No disponible."}

    # 1. Cargar Datos Internos
    df_ventas = cargar_csv(URL_VENTAS)
    df_extra = cargar_csv(URL_NUEVA)
    
    # 2. Cargar PDF (Si hay)
    texto_pdf = ""
    if file:
        try:
            content = await file.read()
            pdf_file = io.BytesIO(content)
            reader = pypdf.PdfReader(pdf_file)
            for i, page in enumerate(reader.pages):
                texto_pdf += f"[Página {i+1}] {page.extract_text()}\n"
        except Exception as e:
            texto_pdf = f"Error PDF: {e}"

    # 3. BÚSQUEDA WEB AUTOMÁTICA
    info_web = buscar_en_web(pregunta)

    # 4. Armar el Prompt Maestro
    contexto = f"""Eres un asistente experto del MinCYT.
    
    FUENTES DE INFORMACIÓN:
    
    A. BÚSQUEDA WEB RECIENTE (Para actualidad):
    {info_web}
    
    B. DATOS INTERNOS (CSV):
    -- Ventas: {df_ventas.tail(50).to_csv(index=False) if df_ventas is not None else 'N/A'}
    -- Extra: {df_extra.to_csv(index=False) if df_extra is not None else 'N/A'}
    
    C. DOCUMENTO ADJUNTO (PDF):
    {texto_pdf[:30000] if texto_pdf else 'Ninguno'}
    
    PREGUNTA DEL USUARIO: {pregunta}
    
    INSTRUCCIONES:
    - Usa la 'BÚSQUEDA WEB' si te preguntan sobre hechos actuales (dólar, clima, noticias) o datos que no están en los archivos.
    - Usa los 'DATOS INTERNOS' para preguntas sobre gestión, proyectos o presupuesto.
    """

    try:
        response = model.generate_content(contexto)
        return {"respuesta": response.text}
    except Exception as e:
        return {"respuesta": f"Error: {e}"}