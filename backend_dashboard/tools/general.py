from langchain_community.tools.tavily_search import TavilySearchResults
# Importamos la configuración que creaste en el paso anterior
from core.config import settings

def get_search_tool():
    """
    Configura y devuelve la herramienta de búsqueda en Internet (Tavily).
    Usa la API KEY centralizada en core/config.py
    """
    return TavilySearchResults(
        tavily_api_key=settings.TAVILY_API_KEY,
        max_results=3 # Trae los 3 mejores resultados
    )