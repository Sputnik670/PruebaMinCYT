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

# --- CONFIGURACIÓN DE LA IA ROBUSTA ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
model = None
last_error_log = "" # Variable para guardar el chisme del error

def configurar_modelo():
    global last_error_log
    if not GEMINI_API_KEY:
        last_error_log = "Variable GEMINI_API_KEY no encontrada en Render."
        print(f"⚠️ {last_error_log}")
        return None

    genai.configure(api_key=GEMINI_API_KEY)
    
    # Lista ampliada de candidatos (con y sin prefijo 'models/')
    candidates = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-1.0-pro",
        "gemini-pro",
        "models/gemini-1.5-flash",
        "models/gemini-pro"
    ]

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }

    tools_config = [{"google_search": {}}] 

    print("🔄 Iniciando protocolo de selección de modelo IA...")
    error_accumulado = []

    for model_name in candidates:
        try:
            print(f"🧪 Probando modelo: {model_name}...")
            # INTENTO A: Con Herramientas
            try:
                m = genai.GenerativeModel(model_name, tools=tools_config, safety_settings=safety_settings)
                m.generate_content("test") 
                print(f"✅ ÉXITO TOTAL: {model_name}")
                return m
            except Exception as e_tools:
                error_accumulado.append(f"{model_name} (Tools): {str(e_tools)}")

            # INTENTO B: Modo Estándar
            m = genai.GenerativeModel(model_name, safety_settings=safety_settings)
            m.generate_content("test")
            print(f"✅ ÉXITO PARCIAL: {model_name}")
            return m

        except Exception as e:
            error_str = f"{model_name} (Std): {str(e)}"
            print(f"❌ {error_str}")
            error_accumulado.append(error_str)
            continue
    
    last_error_log = " | ".join(error_accumulado)
    print(f"💀 FATAL: {last_error_log}")
    return None

# Inicializamos el modelo
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
    return {"status": "online", "mensaje": "Backend V9.1 - Debugging Mode"}

@app.get("/api/dashboard")
def get_dashboard_data():
    # (Lógica igual...)
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
    # Intentar revivir el modelo si murió
    if not model:
        model = configurar_modelo()
        if not model:
            # AQUÍ ESTÁ EL CAMBIO: Devolvemos el detalle del error para que el usuario lo vea
            msg_error = f"❌ Error Crítico de Conexión IA. Detalles técnicos: {last_error_log[:500]}..." 
            return {"respuesta": msg_error}

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

    contexto = """Eres un asistente inteligente del MinCYT.
    FUENTES DE INFORMACIÓN:
    1. DATOS INTERNOS (CSV adjuntos).
    2. ARCHIVOS USUARIO (PDF adjunto).
    3. INTERNET (Google Search): Úsalo si la pregunta requiere datos de actualidad o externos.
    
    DATOS:
    """
    
    if df_ventas is not None:
        contexto += f"--- VENTAS (Resumen) ---\n{df_ventas.head(50).to_csv(index=False)}\n\n"
    if df_extra is not None:
        contexto += f"--- CALENDARIO/EXTRA (Resumen) ---\n{df_extra.head(50).to_csv(index=False)}\n\n"
        
    if texto_pdf_usuario:
        contexto += f"--- ARCHIVO ADJUNTO ({nombre_archivo}) ---\n{texto_pdf_usuario[:50000]}\n\n"
        
    contexto += f"PREGUNTA: {pregunta}\nRESPUESTA:"

    try:
        response = model.generate_content(contexto)
        return {"respuesta": response.text}
    except Exception as e:
        return {"respuesta": f"Error en la IA ({type(e).__name__}): {str(e)}"}