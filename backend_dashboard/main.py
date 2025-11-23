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
modelo_nombre_final = "Ninguno"

def configurar_modelo():
    global modelo_nombre_final
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
        print("🔍 Buscando modelos disponibles...")
        listado_modelos = list(genai.list_models())
        modelos_validos = [m.name for m in listado_modelos if 'generateContent' in m.supported_generation_methods]
        
        if not modelos_validos: return None

        # Preferencia: Flash > 1.5 > Pro
        elegido = next((m for m in modelos_validos if 'flash' in m), None)
        if not elegido: elegido = next((m for m in modelos_validos if '1.5' in m), None)
        if not elegido: elegido = modelos_validos[0]

        print(f"🚀 Modelo seleccionado: {elegido}")
        modelo_nombre_final = elegido
        return genai.GenerativeModel(elegido, safety_settings=safety)

    except Exception as e:
        print(f"❌ Error configuración IA: {e}")
        return None

model = configurar_modelo()

# --- BÚSQUEDA WEB ---
def buscar_en_web(consulta, max_results=3):
    try:
        print(f"🌍 Buscando: {consulta}")
        with DDGS() as ddgs:
            results = list(ddgs.text(consulta, max_results=max_results))
        
        if not results: return "ERROR_BUSQUEDA: No se obtuvieron resultados (posible bloqueo)."
        
        texto = ""
        for i, r in enumerate(results):
            texto += f"- {r['title']}: {r['body']} (Fuente: {r['href']})\n"
        return texto
    except Exception as e:
        print(f"⚠️ Error Web Search: {e}")
        return f"ERROR_BUSQUEDA: Falló la conexión ({str(e)})."

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
    except: return None

@app.get("/")
def home():
    return {"status": "online", "modelo": modelo_nombre_final}

@app.get("/api/dashboard")
def get_dashboard_data():
    # (Lógica dashboard igual...)
    df_bitacora = cargar_csv(URL_BITACORA)
    datos_bitacora = df_bitacora.to_dict(orient="records") if df_bitacora is not None else []
    df_ventas = cargar_csv(URL_VENTAS)
    datos_ventas_crudos = df_ventas.to_dict(orient="records") if df_ventas is not None else []
    datos_tendencia = [] 
    if df_ventas is not None:
        pass # Simplificado
    df_nueva = cargar_csv(URL_NUEVA)
    datos_nueva_tabla = df_nueva.to_dict(orient="records") if df_nueva is not None else []
    df_cal = cargar_csv(URL_CALENDARIO)
    datos_calendario = df_cal.to_dict(orient="records") if df_cal is not None else []

    return {
        "bitacora": datos_bitacora, "ventas_tabla": datos_ventas_crudos,
        "tendencia_grafico": datos_tendencia, "extra_tabla": datos_nueva_tabla, "calendario": datos_calendario
    }

@app.post("/api/chat")
async def chat_con_datos(pregunta: str = Form(...), file: UploadFile = File(None)):
    global model
    if not model:
        model = configurar_modelo()
        if not model: return {"respuesta": "❌ Error IA: No disponible."}

    df_ventas = cargar_csv(URL_VENTAS)
    df_extra = cargar_csv(URL_NUEVA)
    
    texto_pdf = ""
    if file:
        try:
            content = await file.read()
            reader = pypdf.PdfReader(io.BytesIO(content))
            for page in reader.pages: texto_pdf += page.extract_text()
        except: pass

    # Intentar búsqueda web
    info_web = buscar_en_web(pregunta)

    # --- CONTEXTO ÉTICO ANTI-ALUCINACIÓN ---
    contexto = f"""Eres un asistente experto del MinCYT.
    
    ESTADO DE LA BÚSQUEDA WEB:
    {info_web}
    
    DATOS INTERNOS (CSV):
    -- Ventas: {df_ventas.tail(50).to_csv(index=False) if df_ventas is not None else 'N/A'}
    -- Extra: {df_extra.to_csv(index=False) if df_extra is not None else 'N/A'}
    
    PDF ADJUNTO:
    {texto_pdf[:30000]}
    
    PREGUNTA: {pregunta}
    
    REGLAS DE RESPUESTA OBLIGATORIAS:
    1. DATOS INTERNOS: Úsalos siempre que la pregunta sea sobre gestión, proyectos o presupuesto del ministerio.
    
    2. DATOS EXTERNOS (Web):
       - Si 'ESTADO DE LA BÚSQUEDA WEB' contiene resultados reales, úsalos para responder.
       - Si dice 'ERROR_BUSQUEDA' o no hay resultados útiles:
         A) Si preguntan por un DATO DINÁMICO (ej: precio bitcoin hoy, clima ahora, noticia de ayer), DI CLARAMENTE: "No puedo acceder a internet en este momento para darte el dato en tiempo real". NO INVENTES UN VALOR.
         B) Si preguntan por CONOCIMIENTO GENERAL ESTÁTICO (ej: qué es bitcoin, quién fue Einstein, historia), responde con tu conocimiento base.
    
    3. NO ALUCINES FECHAS NI MONTOS si no están en los CSV o en la Web.
    """

    try:
        response = model.generate_content(contexto)
        return {"respuesta": response.text}
    except Exception as e:
        return {"respuesta": f"Error IA: {e}"}