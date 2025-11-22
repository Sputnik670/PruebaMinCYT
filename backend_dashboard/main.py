import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import io
import requests
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import os

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
    """
    Intenta configurar el mejor modelo posible con capacidad de búsqueda (Tools).
    """
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
        # Buscamos modelos que soporten 'generateContent'
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        print(f"📋 Modelos disponibles: {available}")

        # Prioridad 1: Gemini 1.5 Flash (Rápido y soporta Tools)
        target_model = next((m for m in available if 'gemini-1.5-flash' in m), None)
        
        # Prioridad 2: Gemini 1.5 Pro
        if not target_model:
            target_model = next((m for m in available if 'gemini-1.5-pro' in m), None)
            
        # Prioridad 3: Gemini Pro (Clásico)
        if not target_model:
            target_model = 'models/gemini-pro'

        print(f"🚀 Intentando cargar: {target_model}")
        
        # Intentamos cargar CON herramientas de búsqueda
        try:
            # Esta es la línea mágica para 'Deep Research' (Grounding)
            tools_config = [
                {"google_search": {}} # Habilita la búsqueda en Google
            ]
            m = genai.GenerativeModel(target_model, tools=tools_config, safety_settings=safety_settings)
            # Prueba de fuego (dummy)
            m.generate_content("test") 
            print(f"✅ Modelo {target_model} cargado CON Búsqueda Web activa.")
            return m
        except Exception as e_tools:
            print(f"⚠️ No se pudo activar Búsqueda Web en {target_model}: {e_tools}")
            print("🔄 Reintentando en modo estándar (Solo datos internos)...")
            # Fallback: Cargar sin herramientas
            m = genai.GenerativeModel(target_model, safety_settings=safety_settings)
            return m

    except Exception as e:
        print(f"❌ Error crítico configurando IA: {e}")
        return None

# Inicializamos el modelo al arrancar
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
        print(f"Error cargando CSV {url}: {e}")
        return None

class ChatMessage(BaseModel):
    pregunta: str

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Backend V5.0 - IA Híbrida (Datos + Web)"}

@app.get("/api/dashboard")
def get_dashboard_data():
    # 1. Bitácora
    df_bitacora = cargar_csv(URL_BITACORA)
    datos_bitacora = df_bitacora.to_dict(orient="records") if df_bitacora is not None else []

    # 2. Ventas
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

    # 3. Nueva Tabla
    df_nueva = cargar_csv(URL_NUEVA)
    datos_nueva_tabla = df_nueva.to_dict(orient="records") if df_nueva is not None else []

    # 4. Calendario
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
def chat_con_datos(mensaje: ChatMessage):
    global model
    # Reintentar carga si falló al inicio
    if not model:
        model = configurar_modelo()
        if not model:
            return {"respuesta": "❌ Error: No se pudo iniciar el motor de IA."}

    df_ventas = cargar_csv(URL_VENTAS)
    df_bitacora = cargar_csv(URL_BITACORA)
    df_extra = cargar_csv(URL_NUEVA)
    
    contexto = "Eres un analista experto del MinCYT. Tienes acceso a dos fuentes de información:\n"
    contexto += "1. DATOS INTERNOS (Prioritarios): Los CSV adjuntos abajo.\n"
    contexto += "2. BÚSQUEDA WEB: Puedes buscar en Google si la pregunta requiere contexto externo (ej: tipo de cambio, noticias relacionadas).\n\n"
    contexto += "DATOS DEL DASHBOARD:\n"
    
    if df_ventas is not None:
        contexto += f"--- VENTAS (Resumen) ---\n{df_ventas.head(50).to_csv(index=False)}\n\n"
    if df_bitacora is not None:
        contexto += f"--- BITÁCORA (Resumen) ---\n{df_bitacora.head(50).to_csv(index=False)}\n\n"
    if df_extra is not None:
        contexto += f"--- CALENDARIO/EXTRA (Resumen) ---\n{df_extra.head(50).to_csv(index=False)}\n\n"
        
    contexto += f"PREGUNTA USUARIO: {mensaje.pregunta}\n"
    contexto += "RESPUESTA:"

    try:
        response = model.generate_content(contexto)
        return {"respuesta": response.text}
    except Exception as e:
        return {"respuesta": f"Error en el procesamiento: {str(e)}"}