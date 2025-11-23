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
last_error = ""

def configurar_modelo():
    global last_error
    if not GEMINI_API_KEY:
        last_error = "Falta API Key en variables de entorno."
        print(f"⚠️ {last_error}")
        return None

    genai.configure(api_key=GEMINI_API_KEY)
    
    safety = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }

    candidatos = [
        'gemini-1.5-flash',
        'gemini-1.5-pro',
        'gemini-1.0-pro',
        'gemini-pro'
    ]

    print("🔄 Iniciando conexión con IA...")
    for nombre in candidatos:
        try:
            print(f"🧪 Probando modelo: {nombre}")
            m = genai.GenerativeModel(nombre, safety_settings=safety)
            m.generate_content("Test")
            print(f"✅ Conectado exitosamente a: {nombre}")
            return m
        except Exception as e:
            print(f"❌ Falló {nombre}: {e}")
            last_error = f"Falló {nombre}: {str(e)}"
            continue
            
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
    return {"status": "online", "mensaje": "Backend V14 - Full Context Mode"}

@app.get("/api/dashboard")
def get_dashboard_data():
    # (Lógica Dashboard intacta)
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
            return {"respuesta": f"❌ Error IA: No se pudo conectar. {last_error}"}

    df_ventas = cargar_csv(URL_VENTAS)
    df_extra = cargar_csv(URL_NUEVA)
    df_bitacora = cargar_csv(URL_BITACORA)
    
    texto_pdf = ""
    nombre_archivo = ""
    if file:
        try:
            nombre_archivo = file.filename
            content = await file.read()
            pdf_file = io.BytesIO(content)
            reader = pypdf.PdfReader(pdf_file)
            for i, page in enumerate(reader.pages):
                texto_pdf += f"[Página {i+1}] {page.extract_text()}\n"
        except Exception as e:
            texto_pdf = f"Error PDF: {e}"

    # --- CAMBIO CLAVE: ELIMINAMOS .head(30) PARA QUE LEA TODO ---
    contexto = f"""Eres un asistente experto del MinCYT. Analiza TODOS los datos provistos.
    
    FUENTES DE DATOS COMPLETAS:
    
    1. VENTAS E INVERSIÓN (CSV):
    {df_ventas.to_csv(index=False) if df_ventas is not None else 'No disponible'}
    
    2. CALENDARIO Y DATOS EXTRA (CSV):
    {df_extra.to_csv(index=False) if df_extra is not None else 'No disponible'}
    
    3. BITÁCORA DE HORAS (CSV):
    {df_bitacora.to_csv(index=False) if df_bitacora is not None else 'No disponible'}
    
    4. DOCUMENTO ADJUNTO (PDF):
    {texto_pdf[:50000] if texto_pdf else 'Ninguno'}
    
    PREGUNTA DEL USUARIO: {pregunta}
    RESPUESTA:"""

    try:
        response = model.generate_content(contexto)
        return {"respuesta": response.text}
    except Exception as e:
        return {"respuesta": f"Error IA: {e}"}