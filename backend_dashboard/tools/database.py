import os
from supabase import create_client, Client
import logging
from langchain_core.tools import tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

# --- DEFINICIÓN DE MOCK CLIENT (Para evitar caídas si falla la conexión) ---
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
    @property
    def data(self): return []

# --- 1. CONFIGURACIÓN DE SUPABASE GLOBAL (CORREGIDA) ---
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

if not url or not key:
    logger.error("❌ ERROR CRÍTICO: Faltan credenciales de Supabase. Usando Mock.")
    supabase = MockClient()
else:
    # CASO FELIZ: Hay credenciales, conectamos.
    try:
        supabase: Client = create_client(url, key)
        logger.info("✅ Conexión global a Supabase establecida.")
    except Exception as e:
        logger.error(f"❌ Error conectando a Supabase: {e}")
        supabase = MockClient()

# --- 2. CLIENTE FRESCO PARA BACKGROUND TASKS ---
def get_fresh_supabase_client() -> Client:
    """
    Crea un cliente nuevo para tareas asíncronas (audios), evitando conflictos de hilos.
    """
    url_local = os.getenv("SUPABASE_URL")
    key_local = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    
    if not url_local or not key_local:
         return MockClient()
         
    return create_client(url_local, key_local)

# --- 3. MODELOS IA ---
try:
    embeddings_model = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004", 
        task_type="retrieval_query"
    )
except Exception:
    logger.warning("⚠️ Modelo 004 no disponible, fallback a embedding-001")
    embeddings_model = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001", 
        task_type="retrieval_query"
    )

llm_reformulador = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    temperature=0.3,
    max_retries=2
)

# --- 4. FUNCIONES INTERNAS (ACTAS) ---

def guardar_acta(transcripcion: str, resumen: str = None):
    try:
        db_client = get_fresh_supabase_client() 
        titulo = "Reunión: " + (transcripcion[:40] + "..." if len(transcripcion) > 40 else transcripcion)
        data = {"transcripcion": transcripcion, "resumen_ia": resumen, "titulo": titulo}
        
        logger.info(f"💾 Guardando acta en background: {titulo}")
        res = db_client.table("actas_reunion").insert(data).execute()
        
        # Verificación robusta
        if res.data or (hasattr(res, 'count') and res.count):
            logger.info("✅ Acta guardada correctamente.")
            return res.data
        return None
    except Exception as e:
        logger.error(f"❌ Error guardando acta: {e}", exc_info=True) 
        return None

def obtener_historial_actas():
    try:
        # Ahora 'supabase' siempre está definido (sea real o mock)
        response = supabase.table("actas_reunion").select("*").order("created_at", desc=True).limit(10).execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error leyendo actas: {e}")
        return []

def borrar_acta(id_acta: int):
    try:
        supabase.table("actas_reunion").delete().eq("id", id_acta).execute()
        return True
    except Exception as e:
        logger.error(f"Error borrando acta {id_acta}: {e}")
        return False

# --- 5. HERRAMIENTAS DEL AGENTE (TOOLS) ---

@tool
def consultar_actas_reuniones(query: str):
    """Usa esto si preguntan 'qué se habló en la reunión', 'decisiones tomadas' o historial."""
    actas = obtener_historial_actas()
    if not actas: return "No hay actas registradas."
    texto = "--- HISTORIAL REUNIONES ---\n"
    for a in actas:
        fecha = a.get('created_at', '')[:10]
        titulo = a.get('titulo', 'Sin título')
        resumen = a.get('resumen_ia') or a.get('transcripcion', '')[:200]
        texto += f"- [{fecha}] {titulo}: {resumen}...\n"
    return texto

@tool
def consultar_biblioteca_documentos(pregunta: str):
    """
    Busca información en documentos subidos (PDF, Excel, Word).
    """
    try:
        # 1. Expandir consulta
        prompt_expansion = (
            f"Genera una consulta de búsqueda semántica optimizada para: '{pregunta}'. "
            f"Solo devuelve el texto."
        )
        consulta_optimizada = llm_reformulador.invoke(prompt_expansion).content.strip()
        
        # 2. Vectorizar
        vector_pregunta = embeddings_model.embed_query(consulta_optimizada)
        
        # 3. Buscar (RPC)
        response = supabase.rpc(
            "buscar_documentos", 
            {
                "query_embedding": vector_pregunta,
                "match_threshold": 0.45, 
                "match_count": 6
            }
        ).execute()
        
        if not response.data:
            return f"No se encontraron documentos relevantes para '{consulta_optimizada}'."
            
        contexto = f"--- RESULTADOS DOCUMENTOS ---\n"
        for doc in response.data:
            archivo = doc.get('metadata', {}).get('source', 'Desconocido')
            contenido = doc.get('content', '').replace('\n', ' ')
            contexto += f"📄 {archivo}: ...{contenido[:500]}...\n\n"
            
        return contexto

    except Exception as e:
        logger.error(f"Error biblioteca: {e}")
        return f"Error técnico consultando documentos: {str(e)}"

@tool
def guardar_conocimiento(texto: str, etiqueta: str = "Aprendizaje Chat"):
    """Guarda un dato en memoria a largo plazo."""
    try:
        vector = embeddings_model.embed_query(texto)
        registro = {
            "content": texto,
            "metadata": {"source": "Memoria Chat", "type": etiqueta},
            "embedding": vector
        }
        supabase.table("libreria_documentos").insert(registro).execute()
        return "✅ Dato memorizado."
    except Exception as e:
        logger.error(f"Error guardando memoria: {e}")
        return "Error técnico al guardar."