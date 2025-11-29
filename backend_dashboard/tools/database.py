import os
from supabase import create_client, Client
import logging
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Conexión a Supabase usando Variables de Entorno
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

supabase: Client = None

if url and key:
    try:
        supabase = create_client(url, key)
        logger.info("✅ Conexión a Supabase exitosa (Producción)")
    except Exception as e:
        logger.error(f"❌ Error conectando a Supabase: {e}")

def guardar_acta(transcripcion: str, resumen: str = None):
    """Guarda una nueva acta en la base de datos"""
    if not supabase: return None
    try:
        titulo_auto = "Reunión: " + transcripcion[:30] + "..."
        data = {
            "transcripcion": transcripcion,
            "resumen_ia": resumen,
            "titulo": titulo_auto
        }
        response = supabase.table("actas_reunion").insert(data).execute()
        # En versiones nuevas de supabase-py, response.data es la lista insertada
        return response.data
    except Exception as e:
        logger.error(f"Error guardando: {e}")
        return None

def obtener_historial_actas():
    """Recupera las últimas actas para el dashboard"""
    if not supabase: return []
    try:
        response = supabase.table("actas_reunion").select("*").order("created_at", desc=True).limit(10).execute()
        return response.data
    except Exception as e:
        logger.error(f"Error leyendo: {e}")
        return []

def borrar_acta(id_acta: int):
    if not supabase: return False
    try:
        response = supabase.table("actas_reunion").delete().eq("id", id_acta).execute()
        return len(response.data) > 0
    except Exception as e:
        logger.error(f"Error borrando: {e}")
        return False

# --- HERRAMIENTA CRÍTICA PARA EL AGENTE ---
@tool
def consultar_base_de_datos_actas(consulta: str):
    """
    ÚTIL para buscar información en actas de reuniones pasadas, decisiones o historial.
    Retorna el contenido de las últimas reuniones registradas.
    """
    try:
        if not supabase:
            return "Error: No hay conexión con la base de datos de actas."

        actas = obtener_historial_actas()
        if not actas:
            return "El sistema consultó la base de datos y NO encontró actas registradas."
        
        texto = "--- MEMORIA DE REUNIONES (BASE DE DATOS) ---\n"
        for acta in actas:
            fecha = str(acta.get('created_at', '')).split('T')[0]
            titulo = acta.get('titulo', 'Sin título')
            contenido = acta.get('transcripcion', '')[:1500] # Aumentamos límite para mejor contexto
            texto += f"ID: {acta.get('id')} | Fecha: {fecha} | Título: {titulo}\nContenido: {contenido}...\n\n"
            
        return texto
    except Exception as e:
        return f"Error técnico consultando la base de datos: {str(e)}"