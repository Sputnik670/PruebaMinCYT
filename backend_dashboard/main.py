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

# --- CONEXIÓN SUPABASE ---
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try: supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except: pass

# --- CONFIGURACIÓN IA (AUTO-DESCUBRIMIENTO) ---
model = None
last_error = "Iniciando..."

def configurar_modelo():
    global last_error
    if not GEMINI_API_KEY:
        last_error = "Falta GEMINI_API_KEY"
        return None

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        safety = {HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH}

        candidatos = [
            'gemini-1.5-flash', 'models/gemini-1.5-flash',
            'gemini-1.5-pro', 'models/gemini-1.5-pro',
            'gemini-pro', 'models/gemini-pro'
        ]

        for nombre in candidatos:
            try:
                m = genai.GenerativeModel(nombre, safety_settings=safety)
                m.generate_content("Ping")
                print(f"✅ IA Conectada: {nombre}")
                return m
            except Exception as e:
                continue
        
        last_error = "No se pudo conectar ningún modelo."
        return None

    except Exception as e:
        last_error = f"Error config: {e}"
        return None

model = configurar_modelo()

# --- SINCRONIZACIÓN ---
@app.post("/api/sync")
def sincronizar():
    if not supabase: return {"status": "error", "msg": "Falta conexión a Supabase"}
    
    try:
        print("📥 Descargando Excel...")
        r = requests.get(URL_CALENDARIO, timeout=20) # Timeout generoso
        r.encoding = 'utf-8'
        df = pd.read_csv(io.BytesIO(r.content))
        
        df.columns = [c.lower().strip() for c in df.columns]
        
        traduccion = {
            "nac/intl": "nac_intl", "título": "titulo", "titulo": "titulo",
            "fecha inicio": "fecha_inicio", "fecha fin": "fecha_fin",
            "lugar": "lugar", "organizador": "organizador",
            "¿pagan?": "pagan", "pagan": "pagan", "pagan?": "pagan",
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
        if datos:
            supabase.table("calendario_internacional").insert(datos).execute()
            
        return {"status": "ok", "msg": f"¡Éxito! {len(datos)} eventos actualizados."}
        
    except Exception as e:
        print(f"❌ Error Sync: {e}")
        return {"status": "error", "msg": f"Error procesando datos: {str(e)}"}

# --- ENDPOINTS ---
@app.get("/api/data")
def get_data():
    if not supabase: return []
    try: 
        return supabase.table("calendario_internacional").select("*").order("fecha_inicio", desc=False).execute().data
    except: return []

@app.post("/api/chat")
async def chat(pregunta: str = Form(...), file: UploadFile = File(None)):
    global model
    if not model: model = configurar_modelo()
    if not model: return {"respuesta": f"❌ Error IA: {last_error}"}
    
    # 1. Datos (Contexto Interno)
    data = get_data()
    ctx_db = tabulate(data, headers="keys", tablefmt="github") if data else "(Sin datos en Calendario)"
    
    # 2. Web (Contexto Externo)
    ctx_web = "(Sin búsqueda)"
    if TAVILY_API_KEY:
        try: 
            tavily = TavilyClient(api_key=TAVILY_API_KEY)
            # Búsqueda advanced para asegurar buenos resultados externos
            res = tavily.search(query=pregunta, search_depth="advanced", max_results=4)
            
            resultados = []
            for r in res.get('results', []):
                resultados.append(f"Título: {r['title']}\nResumen: {r['content']}\nLink: {r['url']}")
            ctx_web = "\n\n".join(resultados)
            
        except Exception as e:
            ctx_web = f"Error buscando en web: {e}"

    # 3. PDF
    ctx_pdf = ""
    if file:
        try:
            content = await file.read()
            pdf = pypdf.PdfReader(io.BytesIO(content))
            for p in pdf.pages[:5]: ctx_pdf += p.extract_text()
        except: pass

    # PROMPT JERÁRQUICO ESTRICTO
    prompt = f"""
    Eres el Asistente Oficial del MinCYT.
    
    TU MISIÓN ES RESPONDER BASÁNDOTE EN EL SIGUIENTE ORDEN DE PRIORIDAD (JERARQUÍA):
    
    1. 🥇 DASHBOARD / CALENDARIO OFICIAL (Verdad Absoluta):
    {ctx_db}
    
    2. 🥈 INTERNET (Para todo lo que NO esté en el Dashboard):
    {ctx_web}
    
    3. 🥉 PDF ADJUNTO (Contexto adicional si se pide):
    {ctx_pdf}
    
    PREGUNTA DEL USUARIO: "{pregunta}"
    
    REGLAS DE RESPUESTA:
    - PASO 1: Busca la respuesta en la TABLA DEL CALENDARIO. Si el evento o la fecha están ahí, responde SOLO con esos datos.
    - PASO 2: Si (y solo si) la respuesta NO está en el calendario (ej: resultados deportivos, clima, noticias generales), usa la información de INTERNET.
    - PASO 3: Si encuentras la respuesta en Internet, dila directamente. No pongas excusas.
    
    Sé profesional pero directo.
    """
    
    try:
        res = model.generate_content(prompt)
        return {"respuesta": res.text}
    except Exception as e: return {"respuesta": f"Error respuesta: {str(e)}"}