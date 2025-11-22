import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import io
import requests
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import os
import pypdf

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURACIÓN DE LA IA ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
model = None

def configurar_modelo():
    if not GEMINI_API_KEY:
        print("⚠️ ADVERTENCIA: No se encontró la variable GEMINI_API_KEY")
        return None

    genai.configure(api_key=GEMINI_API_KEY)
    
    # Configuración de seguridad estándar
    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }

    try:
        print("🔍 Buscando modelos compatibles con herramientas...")
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        print(f"📋 Modelos disponibles: {available}")

        # Prioridad: Gemini 1.5 Flash (Suele tener mejor soporte de herramientas gratuito)
        target_model = next((m for m in available if 'gemini-1.5-flash' in m), None)
        
        if not target_model:
             target_model = next((m for m in available if 'gemini-1.5-pro' in m), None)

        if not target_model:
            target_model = 'models/gemini-pro'

        print(f"🚀 Intentando cargar: {target_model}")
        
        try:
            # Habilitamos explícitamente la búsqueda
            tools_config = [
                {"google_search": {}} 
            ]
            m = genai.GenerativeModel(target_model, tools=tools_config, safety_settings=safety_settings)
            return m
        except Exception as e_tools:
            print(f"⚠️ No se pudo activar Búsqueda Web en {target_model}: {e_tools}")
            # Fallback sin herramientas si falla la configuración de búsqueda
            m = genai.GenerativeModel(target_model, safety_settings=safety_settings)
            return m

    except Exception as e:
        print(f"❌ Error crítico configurando IA: {e}")
        return None

model = configurar_modelo()

# --- TUS ENLACES ---
URL_BITACORA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv"
URL_VENTAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv"
URL_NUEVA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"
URL_CALENDARIO = "TU_LINK_CALENDARIO_AQUI" 

# --- HERRAMIENTAS ---
def limpiar_dinero(valor):
    if pd.isna(valor): return 0.0
    s = str(valor).replace("$", "").replace(" ", "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s) if s else 0.0

def cargar_csv(url):
    try:
        if "TU_LINK" in url: return None
        response = requests.get(url)
        response.raise_for_status()
        df = pd.read_csv(io.BytesIO(response.content), encoding='utf-8')
        df = df.fillna("")
        return df
    except Exception as e:
        return None

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Backend V8.1 - IA Híbrida Reforzada"}

@app.get("/api/dashboard")
def get_dashboard_data():
    # (Lógica sin cambios)
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
            return {"respuesta": "❌ Error: IA no disponible."}

    # 1. Cargar Datos
    df_ventas = cargar_csv(URL_VENTAS)
    df_bitacora = cargar_csv(URL_BITACORA)
    df_extra = cargar_csv(URL_NUEVA)
    
    texto_pdf_usuario = ""
    nombre_archivo = ""
    if file:
        try:
            nombre_archivo = file.filename
            content = await file.read()
            pdf_file = io.BytesIO(content)
            reader = pypdf.PdfReader(pdf_file)
            for i, page in enumerate(reader.pages):
                texto_pdf_usuario += f"[Página {i+1}] {page.extract_text()}\n"
        except Exception as e:
            texto_pdf_usuario = f"Error al leer archivo: {str(e)}"

    # 2. Prompt Mejorado
    contexto = """Eres un asistente inteligente del MinCYT. Tienes dos capacidades principales:
1.  **Analista de Datos Internos:** Usas los CSV adjuntos para responder sobre gestión, ventas y calendario.
2.  **Investigador Web:** Tienes acceso a Google Search. SI LA PREGUNTA ES SOBRE ACTUALIDAD, DATOS EXTERNOS O NO ESTÁ EN LOS CSV, DEBES USAR LA BÚSQUEDA DE GOOGLE para responder con precisión y datos actualizados.

DATOS INTERNOS DISPONIBLES:
"""
    
    if df_ventas is not None:
        contexto += f"--- VENTAS (Resumen) ---\n{df_ventas.head(50).to_csv(index=False)}\n\n"
    if df_extra is not None:
        contexto += f"--- CALENDARIO/EXTRA (Resumen) ---\n{df_extra.head(50).to_csv(index=False)}\n\n"
        
    if texto_pdf_usuario:
        contexto += f"--- ARCHIVO ADJUNTO ({nombre_archivo}) ---\n{texto_pdf_usuario[:50000]}\n\n"
        
    contexto += f"PREGUNTA DEL USUARIO: {pregunta}\n"
    contexto += "Si la respuesta requiere datos externos (ej: cotización del dólar, noticias, clima, bitcoin), USA TU HERRAMIENTA DE BÚSQUEDA."

    try:
        response = model.generate_content(contexto)
        return {"respuesta": response.text}
    except Exception as e:
        return {"respuesta": f"Error en la IA: {str(e)}"}