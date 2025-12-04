import os
import re
import logging
from supabase import create_client, Client
from langchain_core.tools import tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings

logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN ---
# Cliente Mock para evitar caídas si faltan credenciales en dev local
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
    except Exception:
        supabase = MockClient()

# Modelo de Embeddings para consultas (debe coincidir con docs.py)
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

# --- TOOLS ---

@tool
def consultar_actas_reuniones(query: str):
    """Consulta el historial de reuniones grabadas previamente."""
    try:
        response = supabase.table("actas_reunion").select("*").order("created_at", desc=True).limit(5).execute()
        actas = response.data if response.data else []
        
        if not actas: return "No hay actas registradas."
        
        texto = "--- HISTORIAL REUNIONES ---\n"
        for a in actas:
            fecha = a.get('created_at', '')[:10]
            titulo = a.get('titulo', 'Sin título')
            # Preferimos el resumen IA, si no, un trozo de transcripción
            contenido = a.get('resumen_ia') or (a.get('transcripcion', '')[:200] + "...")
            texto += f"- ID {a.get('id')} [{fecha}] {titulo}: {contenido}\n"
        return texto
    except Exception as e:
        return f"Error consultando actas: {e}"

@tool
def consultar_biblioteca_documentos(pregunta: str):
    """
    [DEPARTAMENTO 2: LEGAL Y DOCUMENTAL]
    ÚSALA para leer documentos subidos (PDF, Word, Normativas).
    - Busco por similitud semántica y palabras clave.
    - Úsala si preguntan "¿Qué dice el documento X?", "Busca información sobre...", "Cláusulas de...".
    - Devuelve fragmentos de texto originales. NO inventa.
    """
    try:
        # 1. Vectorizar la pregunta del usuario
        vector_pregunta = embeddings_model.embed_query(pregunta)
        
        # 2. Búsqueda Semántica en Supabase (RPC)
        # Nota: Requiere que la función 'buscar_documentos' exista en tu Supabase.
        response = supabase.rpc(
            "buscar_documentos", 
            {
                "query_embedding": vector_pregunta,
                "match_threshold": 0.40, # Umbral de similitud (0 a 1)
                "match_count": 8         # Traemos más candidatos para filtrar luego
            }
        ).execute()
        
        if not response.data:
            return "No se encontraron documentos relevantes en la biblioteca."

        candidatos = response.data
        
        # 3. Re-Ranking Lógico (Python-side)
        # Si la pregunta menciona un archivo específico (ej: "en el presupuesto"),
        # priorizamos chunks cuyo 'source' coincida.
        palabras_clave = [w.lower() for w in pregunta.split() if len(w) > 4]
        
        def score_extra(doc):
            # Damos puntos extra si el nombre del archivo está en la pregunta
            source = doc.get('metadata', {}).get('source', '').lower()
            if any(p in source for p in palabras_clave):
                return 10
            return 0

        # Ordenamos por (Score Semántico original + Bonus de nombre de archivo)
        # Asumimos que RPC devuelve 'similarity'.
        candidatos.sort(key=lambda x: x.get('similarity', 0) + score_extra(x), reverse=True)

        # 4. Formatear Respuesta para el Agente
        # Tomamos los Top 4 definitivos
        top_docs = candidatos[:4]
        
        contexto = f"--- RESULTADOS DE BÚSQUEDA ({len(top_docs)} fragmentos) ---\n"
        for i, doc in enumerate(top_docs):
            fuente = doc.get('metadata', {}).get('source', 'Desconocido')
            # Limpiamos saltos excesivos para ahorrar tokens
            contenido = doc.get('content', '').replace('\n', ' ').strip()
            # Cortamos si es muy largo
            if len(contenido) > 1000: contenido = contenido[:1000] + "..."
            
            contexto += f"📄 [Doc {i+1}] FUENTE: {fuente}\nCONTENIDO: {contenido}\n\n"
            
        return contexto

    except Exception as e:
        logger.error(f"Error biblioteca: {e}")
        return f"Error técnico consultando documentos: {str(e)}"

# Funciones de soporte para guardar actas (usadas por audio.py)
def guardar_acta(transcripcion: str, resumen: str = None):
    try:
        titulo = "Reunión: " + (transcripcion[:40] + "..." if len(transcripcion) > 40 else transcripcion)
        data = {"transcripcion": transcripcion, "resumen_ia": resumen, "titulo": titulo}
        supabase.table("actas_reunion").insert(data).execute()
    except Exception as e:
        logger.error(f"Error guardando acta: {e}")

def borrar_acta(id_acta: int):
    try:
        supabase.table("actas_reunion").delete().eq("id", id_acta).execute()
        return True
    except Exception: return False

def obtener_historial_actas():
    # Wrapper simple para el endpoint REST si se necesita directo
    return supabase.table("actas_reunion").select("*").order("created_at", desc=True).limit(10).execute().data