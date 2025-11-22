import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import io
import requests
import google.generativeai as genai
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

# Variable global para el modelo
model = None

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    try:
        # Intentamos usar 'gemini-1.5-flash' primero
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Modelo IA configurado: gemini-1.5-flash")
    except Exception as e:
        print(f"⚠️ Error al configurar gemini-1.5-flash: {e}")
        # Si falla, intentamos con 'gemini-pro' como fallback seguro
        try:
            model = genai.GenerativeModel('gemini-pro')
            print("✅ Fallback: Modelo IA configurado como gemini-pro")
        except Exception as e2:
            print(f"❌ Error crítico configurando IA: {e2}")
            model = None
else:
    print("⚠️ ADVERTENCIA: No se encontró la GEMINI_API_KEY en las variables de entorno")

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
    return {"status": "online", "mensaje": "Backend V4.2 - Fix IA Models"}

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
    # Verificación robusta de la API Key y el Modelo
    if not GEMINI_API_KEY:
        return {"respuesta": "⚠️ Error: API Key no configurada en Render."}
    
    # Si el modelo no se inicializó al principio, intentamos una última vez
    global model
    if not model:
        try:
            model = genai.GenerativeModel('gemini-pro') # Intento final con gemini-pro
        except Exception:
            # Si todo falla, listamos los modelos disponibles para debug
            try:
                modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                return {"respuesta": f"❌ Error: No se pudo cargar el modelo. Modelos disponibles: {modelos}"}
            except:
                return {"respuesta": "❌ Error crítico: La API Key parece inválida o no tiene permisos."}

    df_ventas = cargar_csv(URL_VENTAS)
    df_bitacora = cargar_csv(URL_BITACORA)
    df_extra = cargar_csv(URL_NUEVA)
    
    contexto = "Eres un asistente experto en análisis de datos para el Dashboard MinCYT.\n"
    contexto += "Responde preguntas basándote en los siguientes datos:\n\n"
    
    if df_ventas is not None:
        contexto += f"--- VENTAS ---\n{df_ventas.to_csv(index=False)}\n\n"
    if df_bitacora is not None:
        contexto += f"--- BITÁCORA ---\n{df_bitacora.to_csv(index=False)}\n\n"
    if df_extra is not None:
        contexto += f"--- EXTRA ---\n{df_extra.to_csv(index=False)}\n\n"
        
    contexto += f"USUARIO: {mensaje.pregunta}\n"
    contexto += "ASISTENTE:"

    try:
        response = model.generate_content(contexto)
        return {"respuesta": response.text}
    except Exception as e:
        return {"respuesta": f"Hubo un error al generar la respuesta: {str(e)}"}