import os
import re
from supabase import create_client, Client
import logging
from langchain_core.tools import tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN SUPABASE Y MODELOS ---
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

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

if not url or not key:
    supabase = MockClient()
else:
    try:
        supabase: Client = create_client(url, key)
    except Exception as e:
        supabase = MockClient()

# Cliente fresco para background tasks
def get_fresh_supabase_client() -> Client:
    url_local = os.getenv("SUPABASE_URL")
    key_local = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
    if not url_local or not key_local: return MockClient()
    return create_client(url_local, key_local)

# Modelos
try:
    embeddings_model = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004", 
        task_type="retrieval_query"
    )
except Exception:
    embeddings_model = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001", 
        task_type="retrieval_query"
    )

llm_reformulador = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", 
    temperature=0, # Cero creatividad para extraer keywords
)

# --- FUNCIONES DE ACTAS (MANTENIDAS) ---
def guardar_acta(transcripcion: str, resumen: str = None):
    try:
        db_client = get_fresh_supabase_client() 
        titulo = "Reunión: " + (transcripcion[:40] + "..." if len(transcripcion) > 40 else transcripcion)
        data = {"transcripcion": transcripcion, "resumen_ia": resumen, "titulo": titulo}
        res = db_client.table("actas_reunion").insert(data).execute()
        return res.data
    except Exception as e:
        logger.error(f"Error guardando acta: {e}") 
        return None

def obtener_historial_actas():
    try:
        response = supabase.table("actas_reunion").select("*").order("created_at", desc=True).limit(10).execute()
        return response.data if response.data else []
    except Exception: return []

def borrar_acta(id_acta: int):
    try:
        supabase.table("actas_reunion").delete().eq("id", id_acta).execute()
        return True
    except Exception: return False

# --- TOOLS ---

@tool
def consultar_actas_reuniones(query: str):
    """Consulta el historial de reuniones grabadas."""
    actas = obtener_historial_actas()
    if not actas: return "No hay actas registradas."
    texto = "--- HISTORIAL REUNIONES ---\n"
    for a in actas:
        fecha = a.get('created_at', '')[:10]
        titulo = a.get('titulo', 'Sin título')
        contenido = a.get('resumen_ia') or a.get('transcripcion', '')
        texto += f"- ID {a.get('id')} [{fecha}] {titulo}: {contenido[:300]}...\n"
    return texto

@tool
def consultar_biblioteca_documentos(pregunta: str):
    """
    Busca en documentos PDF/Excel subidos.
    Usa búsqueda híbrida (Semántica + Palabras Clave) para mayor precisión.
    """
    try:
        # 1. Extraer palabras clave críticas (Números, Apellidos, Códigos)
        # Usamos una regex simple para capturar números de expedientes o años
        keywords = re.findall(r'\b\d{3,}\b|\b[A-Z]{2,}\b', pregunta.upper())
        
        # 2. Vectorizar pregunta original
        vector_pregunta = embeddings_model.embed_query(pregunta)
        
        # 3. Buscar en BD (Traemos más candidatos para filtrar después)
        response = supabase.rpc(
            "buscar_documentos", 
            {
                "query_embedding": vector_pregunta,
                "match_threshold": 0.35, # Bajamos umbral para traer más opciones
                "match_count": 10        # Traemos 10 candidatos
            }
        ).execute()
        
        if not response.data:
            return "No se encontraron documentos relevantes."

        candidados = response.data
        resultados_finales = []

        # 4. Reranking / Filtrado Lógico (Python-side Hybrid Search)
        if keywords:
            # Si hay keywords (ej: "550"), priorizamos los docs que las tengan
            prioritarios = []
            otros = []
            
            for doc in candidados:
                contenido = doc.get('content', '').upper()
                # Chequeamos si alguna keyword está en el contenido
                if any(k in contenido for k in keywords):
                    prioritarios.append(doc)
                else:
                    otros.append(doc)
            
            # Ordenamos: primero los que tienen match exacto, luego el resto
            resultados_finales = prioritarios + otros
        else:
            resultados_finales = candidados

        # 5. Formatear respuesta (Top 5 mejores)
        contexto = f"--- RESULTADOS DOCUMENTOS (Top {min(5, len(resultados_finales))}) ---\n"
        for doc in resultados_finales[:5]:
            archivo = doc.get('metadata', {}).get('source', 'Desconocido')
            # Limpiamos saltos de línea excesivos para ahorrar tokens
            contenido = doc.get('content', '').replace('\n', ' ').strip()
            contexto += f"📄 FUENTE: {archivo}\nCONTENIDO: ...{contenido[:800]}...\n\n"
            
        return contexto

    except Exception as e:
        logger.error(f"Error biblioteca: {e}")
        return f"Error consultando documentos: {str(e)}"