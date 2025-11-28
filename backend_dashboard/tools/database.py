import os
from supabase import create_client, Client
import logging

logger = logging.getLogger(__name__)

# Singleton de conexión
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

supabase: Client = None

if url and key:
    try:
        supabase = create_client(url, key)
        logger.info("✅ Conexión a Supabase exitosa")
    except Exception as e:
        logger.error(f"❌ Error conectando a Supabase: {e}")

def guardar_acta(transcripcion: str, resumen: str = None):
    """Guarda una nueva acta en la base de datos"""
    if not supabase:
        logger.warning("Supabase no configurado. No se guardaron datos.")
        return None
    
    try:
        # Generamos un título automático basado en las primeras palabras
        titulo_auto = "Reunión: " + transcripcion[:30] + "..."
        
        data = {
            "transcripcion": transcripcion,
            "resumen_ia": resumen, # Por ahora guardamos lo mismo o null
            "titulo": titulo_auto
        }
        
        response = supabase.table("actas_reunion").insert(data).execute()
        logger.info(f"💾 Acta guardada con ID: {response.data[0]['id']}")
        return response.data
    except Exception as e:
        logger.error(f"Error guardando en Supabase: {e}")
        return None

def obtener_historial_actas():
    """Recupera las últimas actas para el dashboard"""
    if not supabase: return []
    try:
        # Traemos las últimas 10, ordenadas por fecha descendente
        response = supabase.table("actas_reunion").select("*").order("created_at", desc=True).limit(10).execute()
        return response.data
    except Exception as e:
        logger.error(f"Error leyendo Supabase: {e}")
        return []
    
def borrar_acta(id_acta: int):
    """Elimina un acta por su ID"""
    if not supabase: return False
    try:
        response = supabase.table("actas_reunion").delete().eq("id", id_acta).execute()
        # Verificar si se borró algo (la lista data no debería estar vacía)
        if len(response.data) > 0:
            logger.info(f"🗑️ Acta {id_acta} eliminada correctamente.")
            return True
        else:
            logger.warning(f"No se encontró el acta {id_acta} para eliminar.")
            return False
    except Exception as e:
        logger.error(f"Error borrando de Supabase: {e}")
        return False
    
def obtener_actas_como_texto():
    """Convierte el historial de actas en un texto legible para la IA"""
    # Utilizamos la función existente para obtener los datos
    actas = obtener_historial_actas()
    if not actas:
        return "No hay registros de reuniones anteriores."
    
    texto_contexto = "--- HISTORIAL DE REUNIONES (MEMORIA) ---\n"
    for acta in actas:
        # Hacemos una limpieza de fecha simple
        fecha = str(acta.get('created_at', '')).split('T')[0]
        titulo = acta.get('titulo', 'Sin título')
        # Usamos el resumen si existe, sino, los primeros 200 caracteres de la transcripción
        resumen = acta.get('resumen_ia') or acta.get('transcripcion', '')[:200] + "..."
        
        texto_contexto += f"ID: {acta.get('id', 'N/A')} | Fecha: {fecha} | Título: {titulo}\n"
        texto_contexto += f"Resumen/Contenido: {resumen}\n\n"
    
    return texto_contexto