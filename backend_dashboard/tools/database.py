import os
from supabase import create_client, Client
import logging
from langchain_core.tools import tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

# Configuración
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Modelo de embeddings
embeddings_model = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004", 
    task_type="retrieval_query"
)

# --- NUEVO: LLM pequeño para "pensar" sinónimos antes de buscar ---
llm_reformulador = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    temperature=0.3,
    max_retries=2
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

# --- HERRAMIENTA 2: CONSULTAR BIBLIOTECA (ULTRA MEJORADA) ---
@tool
def consultar_biblioteca_documentos(pregunta: str):
    """
    IMPPRESCINDIBLE: Usa esta herramienta cuando el usuario pregunte sobre información específica contenida
    en archivos subidos, como presupuestos, cronogramas 2026, listas, excel o documentos PDF.
    """
    try:
        # 1. PASO COGNITIVO: Expandir la consulta (Query Expansion)
        # Esto permite encontrar "Presupuesto" si el usuario busca "Plata"
        prompt_expansion = (
            f"Actúa como un bibliotecario experto. Genera una consulta de búsqueda optimizada "
            f"para una base de datos vectorial basada en esta pregunta coloquial del usuario: '{pregunta}'. "
            f"Incluye términos técnicos administrativos si es necesario. "
            f"Solo devuelve la consulta optimizada, nada más."
        )
        consulta_optimizada = llm_reformulador.invoke(prompt_expansion).content.strip()
        logger.info(f"🔍 Búsqueda Docs: '{pregunta}' -> Optimizada: '{consulta_optimizada}'")

        # 2. Convertir la consulta OPTIMIZADA en vector
        vector_pregunta = embeddings_model.embed_query(consulta_optimizada)
        
        # 3. Llamar a la función de búsqueda inteligente en Supabase (RPC)
        response = supabase.rpc(
            "buscar_documentos", 
            {
                "query_embedding": vector_pregunta,
                "match_threshold": 0.45, # Umbral más flexible gracias a la expansión
                "match_count": 8
            }
        ).execute()
        
        if not response.data:
            return f"RESULTADO: No se encontraron documentos internos para '{consulta_optimizada}'."
            
        # 4. Formatear la respuesta
        contexto = f"--- RESULTADOS DE LA BIBLIOTECA INTERNA (Búsqueda: {consulta_optimizada}) ---\n"
        for doc in response.data:
            similitud = round(doc.get('similarity', 0) * 100, 1)
            archivo = doc.get('metadata', {}).get('source', 'Desconocido')
            contenido = doc.get('content', '')
            contexto += f"📄 [Fuente: {archivo} | Relevancia: {similitud}%]:\n...{contenido}...\n\n"
            
        return contexto

    except Exception as e:
        logger.error(f"Error biblioteca: {e}")
        return f"Error consultando la biblioteca: {str(e)}"