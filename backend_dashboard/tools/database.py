import os
from supabase import create_client, Client
import logging
from langchain_core.tools import tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DE SUPABASE GLOBAL (Solo para inicialización y Tools) ---
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

if not url or not key:
    logger.error("❌ ERROR CRÍTICO: Faltan las credenciales de Supabase (URL o KEY).")
    # Es preferible que falle aquí a que intente conectar con None
    # Aseguramos que la variable 'supabase' exista, aunque falle, para que el código compile
    if os.getenv("SUPABASE_URL") and (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")):
        supabase: Client = create_client(url, key)
    else:
        # Simulación de cliente para evitar errores de compilación si las variables faltan
        class MockClient:
            def table(self, name): return self
            def insert(self, data): return self
            def execute(self): return self
            def select(self, *args): return self
            def order(self, *args): return self
            def limit(self, *args): return self
            def eq(self, *args): return self
            def delete(self): return self
            def rpc(self, *args): return self
        supabase = MockClient()
        
# --- NUEVA FUNCIÓN: Obtener un cliente fresco para BackgroundTasks ---
def get_fresh_supabase_client() -> Client:
    """Crea y devuelve un nuevo cliente Supabase."""
    url_local = os.getenv("SUPABASE_URL")
    key_local = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url_local or not key_local:
         raise ValueError("Credenciales de Supabase no disponibles en el entorno para tarea de fondo.")
    return create_client(url_local, key_local)


# Modelo de embeddings (depende de la configuración global)
try:
    embeddings_model = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004", 
        task_type="retrieval_query"
    )
except Exception:
    logger.warning("⚠️ Modelo 004 no disponible, usando fallback a embedding-001")
    embeddings_model = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001", 
        task_type="retrieval_query"
    )

# --- NUEVO: LLM para "pensar" sinónimos antes de buscar ---
llm_reformulador = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    temperature=0.3,
    max_retries=2
)

# --- FUNCIONES DE ACTAS (CORREGIDA LA FUNCIÓN GUARDAR_ACTA) ---
def guardar_acta(transcripcion: str, resumen: str = None):
    """
    Guarda el acta en la tabla 'actas_reunion' utilizando un cliente fresco.
    Esto previene problemas de conexión en tareas asíncronas/background.
    """
    try:
        # 1. Obtener un cliente nuevo y seguro para esta tarea
        db_client = get_fresh_supabase_client() 
        
        titulo = "Reunión: " + transcripcion[:30] + "..."
        data = {"transcripcion": transcripcion, "resumen_ia": resumen, "titulo": titulo}
        
        logger.info(f"💾 Ejecutando inserción en BD (Background) para: {titulo}")
        
        # 2. Ejecutar inserción
        res = db_client.table("actas_reunion").insert(data).execute()
        
        if res.data:
            logger.info(f"✅ Acta guardada con éxito (ID: {res.data[0].get('id')}).")
            return res.data
        
        logger.warning("⚠️ La inserción de acta no devolvió datos de éxito.")
        return None
        
    except Exception as e:
        # El logging es crítico para el debug silencioso
        logger.error(f"❌ Error CRÍTICO al guardar acta en Background: {e}", exc_info=True) 
        return None

def obtener_historial_actas():
    try:
        # Usamos el cliente global 'supabase' aquí, ya que no es una tarea de fondo
        return supabase.table("actas_reunion").select("*").order("created_at", desc=True).limit(10).execute().data
    except Exception as e:
        logger.error(f"Error leyendo actas: {e}")
        return []

def borrar_acta(id_acta: int):
    try:
        return supabase.table("actas_reunion").delete().eq("id", id_acta).execute().data
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

# --- HERRAMIENTA 2: CONSULTAR BIBLIOTECA (RAG) ---
@tool
def consultar_biblioteca_documentos(pregunta: str):
    """
    IMPPRESCINDIBLE: Usa esta herramienta cuando el usuario pregunte sobre información específica contenida
    en archivos subidos, como presupuestos, cronogramas 2026, listas, excel o documentos PDF.
    """
    try:
        # 1. PASO COGNITIVO: Expandir la consulta (Query Expansion)
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
                "match_threshold": 0.45, 
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

# --- HERRAMIENTA 3: MEMORIA ACTIVA (NUEVA) ---
@tool
def guardar_conocimiento(texto: str, etiqueta: str = "Aprendizaje Chat"):
    """
    Úsala cuando el usuario te pida explícitamente RECORDAR o GUARDAR un dato importante para el futuro.
    Ej: "Recuerda que el código del proyecto es 999".
    NO la uses para charla casual.
    """
    try:
        logger.info(f"🧠 Guardando recuerdo: {texto[:50]}...")
        vector = embeddings_model.embed_query(texto)
        registro = {
            "content": texto,
            "metadata": {"source": "Memoria del Asistente", "type": etiqueta},
            "embedding": vector
        }
        supabase.table("libreria_documentos").insert(registro).execute()
        return "✅ Dato guardado exitosamente en mi memoria a largo plazo."
    except Exception as e:
        logger.error(f"Error guardando memoria: {e}")
        return "Error técnico al intentar guardar el recuerdo."