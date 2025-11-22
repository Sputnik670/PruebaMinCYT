import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import io
import requests
import google.generativeai as genai
import os
import pypdf # <--- Nueva librería para leer PDFs

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
    try:
        # Buscamos el mejor modelo disponible (Pro > Flash)
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Prioridad: Gemini Pro
        target_model = next((m for m in available_models if 'gemini-pro' in m and 'vision' not in m), None)
        if not target_model:
            target_model = next((m for m in available_models if 'flash' in m), available_models[0] if available_models else None)

        if target_model:
            print(f"✅ Modelo IA seleccionado: {target_model}")
            return genai.GenerativeModel(target_model)
        else:
            print("❌ No se encontraron modelos compatibles.")
            return None
    except Exception as e:
        print(f"❌ Error crítico configurando IA: {e}")
        return None

model = configurar_modelo()

# --- TUS ENLACES ---
URL_BITACORA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv"
URL_VENTAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv"
URL_NUEVA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"
URL_CALENDARIO = "TU_LINK_CALENDARIO_AQUI" 

# 👇 ¡NUEVO: PEGA AQUÍ EL LINK DIRECTO DE TU PDF! 👇
# Nota: Si es Google Drive, asegúrate de usar un link de descarga directa, no de vista previa.
URL_DOCUMENTO_PDF = "TU_LINK_PDF_AQUI" 

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
        print(f"Error CSV {url}: {e}")
        return None

# --- NUEVA FUNCIÓN PARA LEER PDF ---
def cargar_pdf_texto(url):
    try:
        if "TU_LINK" in url or not url: return ""
        print(f"📥 Descargando PDF desde: {url}")
        response = requests.get(url)
        response.raise_for_status()
        
        # Leemos el PDF desde la memoria
        pdf_file = io.BytesIO(response.content)
        reader = pypdf.PdfReader(pdf_file)
        
        texto_completo = ""
        for i, page in enumerate(reader.pages):
            texto_completo += f"--- Página {i+1} ---\n{page.extract_text()}\n"
            
        print(f"✅ PDF procesado exitosamente ({len(reader.pages)} páginas)")
        return texto_completo
    except Exception as e:
        print(f"⚠️ Error leyendo PDF: {e}")
        return ""

class ChatMessage(BaseModel):
    pregunta: str

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Backend V6.0 - Lector de Documentos PDF Activo"}

@app.get("/api/dashboard")
def get_dashboard_data():
    # (Lógica de Dashboard igual que antes para no romper el frontend)
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
def chat_con_datos(mensaje: ChatMessage):
    global model
    if not model:
        model = configurar_modelo()
        if not model:
            return {"respuesta": "❌ Error: IA no disponible. Verifica API Key en Render."}

    # 1. Cargar Datos Numéricos
    df_ventas = cargar_csv(URL_VENTAS)
    df_bitacora = cargar_csv(URL_BITACORA)
    df_extra = cargar_csv(URL_NUEVA)
    
    # 2. Cargar Documento PDF (¡NUEVO!)
    texto_pdf = cargar_pdf_texto(URL_DOCUMENTO_PDF)
    
    # 3. Armar el "Cerebro" del Contexto
    contexto = "Eres un analista experto del MinCYT. Tienes acceso a datos numéricos y documentación oficial.\n"
    contexto += "Responde basándote en la siguiente información:\n\n"
    
    if df_ventas is not None:
        contexto += f"--- DATOS: VENTAS (Resumen) ---\n{df_ventas.head(50).to_csv(index=False)}\n\n"
    if df_extra is not None:
        contexto += f"--- DATOS: CALENDARIO/EXTRA ---\n{df_extra.head(50).to_csv(index=False)}\n\n"
        
    if texto_pdf:
        # Limitamos el texto del PDF a ~30.000 caracteres para no saturar, si es muy largo.
        # Gemini Pro aguanta mucho, pero por seguridad y velocidad.
        contexto += f"--- DOCUMENTACIÓN ADJUNTA (PDF) ---\n{texto_pdf[:30000]}\n...\n(Fin del extracto)\n\n"
    else:
        contexto += "--- DOCUMENTACIÓN (PDF) ---\nNo se pudo cargar o no hay documento asignado.\n\n"
        
    contexto += f"PREGUNTA DEL USUARIO: {mensaje.pregunta}\n"
    contexto += "RESPUESTA:"

    try:
        response = model.generate_content(contexto)
        return {"respuesta": response.text}
    except Exception as e:
        return {"respuesta": f"Error procesando respuesta: {str(e)}"}