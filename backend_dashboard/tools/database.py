import os
from supabase import create_client, Client
import logging
from langchain_core.tools import tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings

logger = logging.getLogger(__name__)

# Configuración
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Modelo de embeddings ACTUALIZADO y más potente
embeddings_model = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004",  # <--- CAMBIO CLAVE: Modelo más reciente
    task_type="retrieval_query"
)

# --- FUNCIONES DE ACTAS (Mantenemos lo que ya tenías) ---
def guardar_acta(transcripcion: str, resumen: str = None):
    try:
        titulo = "Reunión: " + transcripcion[:30] + "..."
        data = {"transcripcion": transcripcion, "resumen_ia": resumen, "titulo": titulo}
        return supabase.table("actas_reunion").insert(data).execute().data
    except Exception as e:
        logger.error(f"Error guardando acta: {e}")
        return None

def obtener_historial_actas():
    try:
        return supabase.table("actas_reunion").select("*").order("created_at", desc=True).limit(10).execute().data
    except Exception as e:
        logger.error(f"Error leyendo actas: {e}")
        return []

def borrar_acta(id_acta: int):
    try:
        res = supabase.table("actas_reunion").delete().eq("id", id_acta).execute()
        return len(res.data) > 0
    except Exception:
        return False

# --- HERRAMIENTA 1: CONSULTAR ACTAS ---
@tool
def consultar_actas_reuniones(query: str):
    """Usa esto si preguntan 'qué se habló en la reunión', 'decisiones tomadas' o historial de audio."""
    actas = obtener_historial_actas()
    if not actas: return "No hay actas registradas."
    texto = "--- HISTORIAL REUNIONES ---\n"
    for a in actas:
        texto += f"Fecha: {a.get('created_at', '')[:10]} | {a.get('titulo')}\nResumen: {a.get('transcripcion')[:500]}...\n\n"
    return texto

# --- HERRAMIENTA 2: CONSULTAR BIBLIOTECA (OPTIMIZADA) ---
@tool
def consultar_biblioteca_documentos(pregunta: str):
    """
    IMPPRESCINDIBLE: Usa esta herramienta cuando el usuario pregunte sobre información específica contenida
    en archivos subidos, como presupuestos, cronogramas 2026, listas, excel o documentos PDF.
    """
    try:
        # 1. Convertir la pregunta del usuario en números (vector)
        vector_pregunta = embeddings_model.embed_query(pregunta)
        
        # 2. Llamar a la función de búsqueda inteligente en Supabase (RPC)
        response = supabase.rpc(
            "buscar_documentos", 
            {
                "query_embedding": vector_pregunta,
                "match_threshold": 0.5, # <--- CAMBIO CLAVE: Bajamos la vara (antes 0.7)
                "match_count": 8        # <--- CAMBIO CLAVE: Más contexto (antes 5)
            }
        ).execute()
        
        if not response.data:
            return "RESULTADO: No se encontraron documentos internos con esa información específica."
            
        # 3. Formatear la respuesta para Pitu con métrica de confianza
        contexto = f"--- RESULTADOS DE LA BIBLIOTECA INTERNA PARA: '{pregunta}' ---\n"
        for doc in response.data:
            similitud = round(doc.get('similarity', 0) * 100, 1) # Extra
            archivo = doc.get('metadata', {}).get('source', 'Desconocido')
            contenido = doc.get('content', '')
            contexto += f"📄 [Fuente: {archivo} | Confianza: {similitud}%]:\n...{contenido}...\n\n"
            
        return contexto

    except Exception as e:
        return f"Error consultando la biblioteca: {str(e)}"