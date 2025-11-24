import pandas as pd
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import io
import os
import requests
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import pypdf
from tavily import TavilyClient
from tabulate import tabulate 
from supabase import create_client, Client
import numpy as np

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- VARIABLES ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

URL_CALENDARIO = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"

# --- CONEXIONES ---
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try: supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except: pass

# --- CONFIGURACIÓN IA INTELIGENTE (AUTO-DESCUBRIMIENTO) ---
model = None
last_error = "Iniciando..."

def configurar_modelo():
    global last_error
    if not GEMINI_API_KEY:
        last_error = "Falta GEMINI_API_KEY."
        return None

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        safety = {HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH}

        # PASO 1: Preguntar a Google qué modelos tiene esta API KEY
        print("🔍 Consultando lista de modelos disponibles a Google...")
        modelos_disponibles = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    modelos_disponibles.append(m.name)
            print(f"📋 Modelos encontrados: {modelos_disponibles}")
        except Exception as e:
            print(f"⚠️ No se pudo listar modelos: {e}")

        # PASO 2: Crear lista de candidatos (Priorizando los encontrados)
        candidatos = []
        
        # Si encontramos modelos reales, los ponemos primero en la lista
        if modelos_disponibles:
            # Preferimos Flash o Pro si existen
            for m in modelos_disponibles:
                if 'flash' in m: candidates_priority = 0
                elif 'pro' in m: candidates_priority = 1
                else: candidates_priority = 2
                candidatos.append((candidates_priority, m))
            candidatos.sort() # Ordenar por prioridad
            candidatos = [x[1] for x in candidatos] # Quedarnos solo con nombres
        
        # Agregamos los clásicos por si acaso falló el listado
        candidatos.extend(['gemini-1.5-flash', 'gemini-pro', 'models/gemini-1.5-flash'])

        # PASO 3: Probar conexión uno por uno
        errores = []
        for nombre in candidatos:
            try:
                print(f"🧪 Probando conexión con: {nombre}...")
                m = genai.GenerativeModel(nombre, safety_settings=safety)
                m.generate_content("Ping")
                print(f"✅ ¡CONEXIÓN EXITOSA CON {nombre}!")
                return m
            except Exception as e:
                errores.append(f"{nombre}: {e}")
                continue
        
        last_error = "No funcionó ningún modelo. Modelos detectados: " + str(modelos_disponibles)
        return None

    except Exception as e:
        last_error = f"Error fatal: {str(e)}"
        return None

model = configurar_modelo()

# --- SINCRONIZACIÓN ---
@app.post("/api/sync")
def sincronizar():
    if not supabase: return {"status": "error", "msg": "Falta Supabase"}
    try:
        r = requests.get(URL_CALENDARIO)
        r.encoding = 'utf-8'
        df = pd.read_csv(io.BytesIO(r.content))
        
        df.columns = [c.lower().strip() for c in df.columns]
        traduccion = {
            "nac/intl": "nac_intl", "título": "titulo", "titulo": "titulo",
            "fecha inicio": "fecha_inicio", "fecha fin": "fecha_fin",
            "lugar": "lugar", "organizador": "organizador",
            "¿pagan?": "pagan", "pagan": "pagan",
            "participante": "participante", "observaciones": "observaciones"
        }
        df.rename(columns=traduccion, inplace=True)
        
        df.replace([np.inf, -np.inf], np.nan, inplace=True)
        df = df.where(pd.notnull(df), None)
        
        for col in ["fecha_inicio", "fecha_fin"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
                df[col] = df[col].replace({np.nan: None})

        cols = ["nac_intl", "titulo", "fecha_inicio", "fecha_fin", "lugar", "organizador", "pagan", "participante", "observaciones"]
        df = df[[c for c in df.columns if c in cols]]
        datos = df.to_dict(orient='records')
        
        supabase.table("calendario_internacional").delete().neq("id", 0).execute()
        if datos: supabase.table("calendario_internacional").insert(datos).execute()
            
        return {"status": "ok", "msg": f"¡Éxito! {len(datos)} eventos actualizados."}
    except Exception as e:
        return {"status": "error", "msg": f"Error Sync: {str(e)}"}

# --- ENDPOINTS ---
@app.get("/api/data")
def get_data():
    if not supabase: return []
    try: return supabase.table("calendario_internacional").select("*").order("fecha_inicio", desc=False).execute().data
    except: return []

@app.post("/api/chat")
async def chat(pregunta: str = Form(...), file: UploadFile = File(None)):
    global model
    
    # Reintento inteligente si no hay modelo cargado
    if not model: model = configurar_modelo()
    
    if not model:
        return {"respuesta": f"❌ Error de IA: {last_error}"}
    
    data = get_data()
    ctx_db = tabulate(data, headers="keys", tablefmt="github") if data else "(Sin datos)"
    
    ctx_web = ""
    if TAVILY_API_KEY:
        try: ctx_web = str(TavilyClient(api_key=TAVILY_API_KEY).search(pregunta, max_results=2))
        except: pass

    ctx_pdf = ""
    if file:
        try:
            content = await file.read()
            pdf = pypdf.PdfReader(io.BytesIO(content))
            for p in pdf.pages[:5]: ctx_pdf += p.extract_text()
        except: pass

    prompt = f"""
    Eres el Asistente MinCYT.
    CALENDARIO (DB): {ctx_db}
    WEB: {ctx_web}
    PDF: {ctx_pdf}
    PREGUNTA: {pregunta}
    """
    
    try:
        res = model.generate_content(prompt)
        return {"respuesta": res.text}
    except Exception as e:
        return {"respuesta": f"Error respuesta: {str(e)}"}