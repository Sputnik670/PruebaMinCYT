import os
import logging
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
logger = logging.getLogger(__name__)

# --- CONEXIÓN SQL (Supabase) ---
url = os.getenv("SUPABASE_URL")

# 1. Prioridad Absoluta: Llave Maestra (Service Role)
# Necesaria para saltarse las reglas de seguridad (RLS) y leer la tabla maestra
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not key:
    # 2. Fallback: Llave Pública (Anon)
    # Si caemos aquí, es muy probable que NO veas datos en la tabla agenda_unificada
    key = os.getenv("SUPABASE_KEY")
    if key:
        logger.warning("⚠️  ADVERTENCIA: Usando llave pública (ANON). Es probable que la tabla 'agenda_unificada' se vea vacía por seguridad.")
    else:
        logger.error("❌ ERROR CRÍTICO: No se encontró ninguna KEY en el archivo .env")

if not url or not key:
    logger.error("❌ Faltan credenciales. El dashboard no funcionará.")
    supabase = None
else:
    try:
        supabase = create_client(url, key)
        # Log de diagnóstico: Nos confirma si estamos usando la llave poderosa o la débil
        es_service = key == os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        tipo = "⚡ SERVICE_ROLE (ADMIN)" if es_service else "zzz ANON (PÚBLICA)"
        logger.info(f"✅ Supabase conectado | URL: ...{url[-5:]} | Llave: {tipo}")
    except Exception as e:
        logger.error(f"❌ Error de conexión Supabase: {e}")
        supabase = None

def get_data_cliente_formatted():
    """
    Recupera la Gestión Interna (Misiones Oficiales) desde SQL.
    """
    if not supabase: return []
    
    try:
        # Consulta directa a la tabla maestra, filtrando por origen
        response = supabase.table("agenda_unificada")\
            .select("*")\
            .eq("origen_dato", "MisionesOficiales")\
            .order("fecha", desc=True)\
            .execute()
            
        return response.data
    except Exception as e:
        logger.error(f"❌ Error leyendo SQL Cliente: {e}")
        return []

def get_data_ministerio_formatted():
    """
    Recupera la Agenda Pública desde SQL.
    """
    if not supabase: return []

    try:
        response = supabase.table("agenda_unificada")\
            .select("*")\
            .eq("origen_dato", "CalendarioPublico")\
            .order("fecha", desc=True)\
            .execute()
            
        return response.data
    except Exception as e:
        logger.error(f"❌ Error leyendo SQL Ministerio: {e}")
        return []

# Mantenemos esta función auxiliar por compatibilidad
def obtener_datos_raw():
    return get_data_cliente_formatted() + get_data_ministerio_formatted()