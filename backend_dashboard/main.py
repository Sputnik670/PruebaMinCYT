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
# Asegúrate de configurar estas variables en Render o en tu entorno local
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")

model = None
tavily_client = None

# --- CONFIGURACIÓN IA (GEMINI) ---
def configurar_modelo():
    if not GEMINI_API_KEY:
        print("⚠️ Falta GEMINI_API_KEY. La IA no funcionará.")
        return None

    genai.configure(api_key=GEMINI_API_KEY)
    
    # Configuración de seguridad ajustada para evitar bloqueos innecesarios en documentos técnicos
    safety = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }

    candidatos = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.0-pro']
    
    for nombre in candidatos:
        try:
            m = genai.GenerativeModel(nombre, safety_settings=safety)
            # Prueba rápida de conexión
            m.generate_content("Ping")
            print(f"✅ IA Conectada exitosamente: {nombre}")
            return m
        except Exception as e:
            print(f"Intento fallido con {nombre}: {e}")
            continue
            
    print("❌ No se pudo conectar con ningún modelo de Gemini.")
    return None

model = configurar_modelo()

# --- CONFIGURACIÓN BÚSQUEDA (TAVILY) ---
if TAVILY_API_KEY:
    try:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        print("✅ Buscador Tavily: ACTIVO")
    except Exception as e:
        print(f"❌ Error iniciando Tavily: {e}")
else:
    print("⚠️ Falta TAVILY_API_KEY. La búsqueda web estará desactivada.")

def buscar_en_web(consulta):
    if not tavily_client:
        return "(Búsqueda web no disponible: Falta API Key)"
    
    try:
        print(f"🌍 Buscando en internet: {consulta}")
        # search_depth="basic" es más rápido, "advanced" es más profundo
        response = tavily_client.search(query=consulta, search_depth="basic", max_results=3)
        
        texto_resultados = "--- RESULTADOS DE BÚSQUEDA WEB (Fuente Externa) ---\n"
        if 'results' in response:
            for r in response['results']:
                texto_resultados += f"Título: {r.get('title', 'N/A')}\n"
                texto_resultados += f"Info: {r.get('content', 'N/A')}\n"
                texto_resultados += f"Fuente: {r.get('url', 'N/A')}\n\n"
        return texto_resultados
    except Exception as e:
        print(f"⚠️ Error en búsqueda: {e}")
        return f"(Error buscando en internet: {e})"

# --- ENLACES DE DATOS (CSV) ---
# Nota: Si el link de calendario no existe, la función cargar_csv lo manejará correctamente.
URL_BITACORA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv"
URL_VENTAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv"
URL_NUEVA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"
URL_CALENDARIO = "TU_LINK_CALENDARIO_AQUI" 

def cargar_csv(url):
    try:
        if not url or "TU_LINK" in url: 
            return None
        response = requests.get(url)
        response.raise_for_status() # Lanza error si el status no es 200
        df = pd.read_csv(io.BytesIO(response.content), encoding='utf-8')
        df = df.fillna("")
        return df
    except Exception as e: 
        # print(f"Info: No se pudo cargar CSV de {url} ({e})")
        return None

@app.get("/")
def home():
    estado_web = "✅ Activo" if tavily_client else "❌ Inactivo (Falta Key)"
    estado_ia = "✅ Activo" if model else "❌ Inactivo (Falta Key)"
    return {"status": "online", "internet": estado_web, "ia": estado_ia}

@app.get("/api/dashboard")
def get_dashboard_data():
    df_bitacora = cargar_csv(URL_BITACORA)
    df_ventas = cargar_csv(URL_VENTAS)
    df_nueva = cargar_csv(URL_NUEVA)
    df_cal = cargar_csv(URL_CALENDARIO)

    # Convertir a diccionarios o listas vacías si falló la carga
    return {
        "bitacora": df_bitacora.to_dict(orient="records") if df_bitacora is not None else [],
        "ventas_tabla": df_ventas.to_dict(orient="records") if df_ventas is not None else [],
        "tendencia_grafico": [], # Puedes agregar lógica aquí si tus CSVs tienen fechas y montos
        "extra_tabla": df_nueva.to_dict(orient="records") if df_nueva is not None else [],
        "calendario": df_cal.to_dict(orient="records") if df_cal is not None else []
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
            return {"respuesta": "❌ Error: La IA no está disponible. Verifica la API KEY en el servidor."}

    # 1. Recuperar Datos Internos (Contexto CSV)
    # Cargamos solo una muestra para no exceder tokens, a menos que uses Gemini 1.5 Pro que aguanta mucho.
    df_ventas = cargar_csv(URL_VENTAS)
    df_bitacora = cargar_csv(URL_BITACORA)
    
    contexto_csv = "--- DATOS INTERNOS DEL MINISTERIO ---\n"
    if df_ventas is not None:
        contexto_csv += f"Tabla de Ventas (últimos 30 registros):\n{df_ventas.tail(30).to_csv(index=False)}\n\n"
    else:
        contexto_csv += "Tabla de Ventas: No disponible.\n"
        
    if df_bitacora is not None:
        contexto_csv += f"Bitácora de Tareas (primeros 20 registros):\n{df_bitacora.head(20).to_csv(index=False)}\n\n"

    # 2. Procesar PDF Adjunto (Contexto Documental)
    texto_pdf = ""
    nombre_archivo = ""
    if file:
        try:
            nombre_archivo = file.filename
            # Leer contenido del archivo en memoria
            content = await file.read()
            pdf_reader = pypdf.PdfReader(io.BytesIO(content))
            
            texto_pdf = f"--- CONTENIDO DEL ARCHIVO ADJUNTO ({nombre_archivo}) ---\n"
            for i, page in enumerate(pdf_reader.pages):
                texto_pdf += page.extract_text() + "\n"
                # Limite de seguridad simple para no enviar libros enteros si el modelo es pequeño
                if len(texto_pdf) > 50000: 
                    texto_pdf += "\n[...Texto truncado por longitud...]"
                    break
        except Exception as e:
            texto_pdf = f"\n[Error al leer el PDF adjunto: {str(e)}]\n"

    # 3. Búsqueda Web (Contexto Externo)
    # Buscamos en internet la pregunta del usuario para tener contexto actualizado
    info_web = buscar_en_web(pregunta)

    # 4. Prompt Maestro
    # Estructuramos la petición para que la IA sepa qué fuente priorizar.
    prompt_final = f"""
    Eres un asistente inteligente para el MinCYT (Ministerio de Ciencia y Tecnología).
    
    Tu misión es responder la PREGUNTA DEL USUARIO basándote en la información disponible.
    
    FUENTES DE INFORMACIÓN DISPONIBLES:
    1. RESULTADOS DE INTERNET (Prioridad para noticias, hechos actuales, definiciones generales):
    {info_web}
    
    2. DOCUMENTOS ADJUNTOS (Prioridad si el usuario pregunta sobre "el archivo", "el pdf" o "este documento"):
    {texto_pdf}
    
    3. DATOS INTERNOS CSV (Prioridad si el usuario pregunta sobre ventas, bitácora, registros internos):
    {contexto_csv}
    
    PREGUNTA DEL USUARIO: "{pregunta}"
    
    INSTRUCCIONES:
    - Si la respuesta está en el PDF adjunto, cítalo.
    - Si la respuesta requiere datos en tiempo real (ej. precio dolar, noticias), usa la información de internet.
    - Si usas los datos CSV, analiza los números brevemente.
    - Si la información no está en ninguna fuente, indica que no tienes esa información.
    - Responde siempre en español y con formato Markdown si es necesario.
    """

    try:
        # Generar respuesta con Gemini
        response = model.generate_content(prompt_final)
        return {"respuesta": response.text}
    except Exception as e:
        return {"respuesta": f"❌ Ocurrió un error al procesar tu solicitud con la IA: {str(e)}"}