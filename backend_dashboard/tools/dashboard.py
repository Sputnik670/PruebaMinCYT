import os
import json
from supabase import create_client, Client
from langchain.tools import tool

# --- CONFIGURACIÓN SUPABASE ---
# Estas variables deben estar en Render
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_CLIENT: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# Variable de estado para la caché (Caché en memoria por 5 minutos)
CACHE = {"data": [], "timestamp": 0}
CACHE_DURATION = 300 # 5 minutos en segundos

def obtener_datos_raw():
    """
    Obtiene datos de la tabla 'calendario' de Supabase (con caché).
    """
    global CACHE

    if not SUPABASE_CLIENT:
        print("❌ ERROR: Cliente Supabase no inicializado. Faltan variables de entorno.")
        return []

    # Verificar caché
    if CACHE["timestamp"] > (os.time() - CACHE_DURATION):
        print("ℹ️ Datos servidos desde la caché.")
        return CACHE["data"]

    print("--- CONSULTANDO SUPABASE ---")
    try:
        # Consulta de ejemplo: trae todos los eventos (se puede mejorar con filtros)
        response = SUPABASE_CLIENT.table('calendario').select("*").execute()
        
        datos = response.data
        
        # Actualizar caché
        CACHE["data"] = datos
        CACHE["timestamp"] = os.time()
        
        print(f"✔ Datos cargados de Supabase: {len(datos)} filas")
        return datos

    except Exception as e:
        print(f"❌ Error al leer los datos de Supabase: {str(e)}")
        return []


@tool
def consultar_calendario(consulta: str):
    """
    Herramienta para consultar agenda y eventos del calendario.
    """
    try:
        print("🔍 Ejecutando herramienta consultar_calendario()...")
        datos = obtener_datos_raw()

        if not datos:
            return "No se pudieron obtener datos del calendario."

        return json.dumps(datos[:15], indent=2, ensure_ascii=False)

    except Exception as e:
        return f"Excepción en herramienta: {str(e)}"