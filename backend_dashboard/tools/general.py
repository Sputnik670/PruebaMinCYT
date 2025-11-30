from langchain_community.tools.tavily_search import TavilySearchResults
from core.config import settings

def get_search_tool():
    """
    Configura y devuelve la herramienta de búsqueda en Internet (Tavily).
    OPTIMIZADA: Modo 'advanced' para respuestas profundas y más resultados.
    """
    return TavilySearchResults(
        tavily_api_key=settings.TAVILY_API_KEY,
        max_results=6,           # Aumentamos de 3 a 6 para tener más contexto
        search_depth="advanced", # CRÍTICO: Busca contenido real, no solo títulos
        include_answer=True,     # Pide a Tavily una respuesta directa procesada
        include_raw_content=True # Permite al LLM leer el contenido crudo si lo necesita
    )