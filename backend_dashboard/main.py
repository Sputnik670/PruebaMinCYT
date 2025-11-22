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
# 👇 ¡PEGA TU API KEY DE GEMINI AQUÍ! 👇
GEMINI_API_KEY = "AIzaSyAR8xfyUCEcIlpeRWG36p7_3CFEsx85958" 

# Configurar la IA si hay clave
if GEMINI_API_KEY != "PEGAR_TU_CLAVE_AQUI":
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

# --- TUS ENLACES ---
URL_BITACORA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv"
URL_VENTAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv"
URL_NUEVA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"
URL_CALENDARIO = "TU_LINK_CALENDARIO_AQUI" # Reemplaza si tienes el link nuevo

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
        # Usamos utf-8 para tildes y decodificamos correctamente
        df = pd.read_csv(io.BytesIO(response.content), encoding='utf-8')
        df = df.fillna("")
        return df
    except Exception as e:
        print(f"Error cargando CSV {url}: {e}")
        return None

# Modelo para recibir el mensaje del chat
class ChatMessage(BaseModel):
    pregunta: str

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Backend V4.0 - Con IA Gemini"}

@app.get("/api/dashboard")
def get_dashboard_data():
    # (Lógica original sin cambios para no romper nada)
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

# --- NUEVO ENDPOINT DE CHAT ---
@app.post("/api/chat")
def chat_con_datos(mensaje: ChatMessage):
    if not model:
        return {"respuesta": "⚠️ Error: No se ha configurado la API Key de Gemini en el servidor."}

    # 1. Recopilar contexto (Leemos los datos frescos)
    df_ventas = cargar_csv(URL_VENTAS)
    df_bitacora = cargar_csv(URL_BITACORA)
    df_extra = cargar_csv(URL_NUEVA)
    
    # Convertimos a texto resumido para que la IA lo lea
    contexto = "Eres un asistente experto en análisis de datos para el Dashboard MinCYT.\n"
    contexto += "Aquí tienes los datos actuales del sistema:\n\n"
    
    if df_ventas is not None:
        contexto += f"--- VENTAS E INVERSIONES ---\n{df_ventas.to_csv(index=False)}\n\n"
    if df_bitacora is not None:
        contexto += f"--- BITÁCORA DE HORAS ---\n{df_bitacora.to_csv(index=False)}\n\n"
    if df_extra is not None:
        contexto += f"--- CALENDARIO/DATOS EXTRA ---\n{df_extra.to_csv(index=False)}\n\n"
        
    contexto += f"PREGUNTA DEL USUARIO: {mensaje.pregunta}\n"
    contexto += "Responde de forma concisa, profesional y basada SOLO en los datos provistos. Si no sabes, dilo."

    try:
        # 2. Preguntar a Gemini
        response = model.generate_content(contexto)
        return {"respuesta": response.text}
    except Exception as e:
        return {"respuesta": f"Hubo un error al consultar a la IA: {str(e)}"}