# Archivo: backend/agent.py

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent, AgentType
from langchain_community.tools.tavily_search import TavilySearchResults

# 1. Cargar variables
load_dotenv()

openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
tavily_api_key = os.getenv("TAVILY_API_KEY")
# Usamos un modelo por defecto, pero permitimos cambiarlo desde .env
model_name = os.getenv("MODEL_NAME", "google/gemini-flash-1.5") 

# Validación de seguridad
if not openrouter_api_key:
    raise ValueError("Falta la OPENROUTER_API_KEY en las variables de entorno")

# 2. Configurar el LLM para usar OpenRouter
llm = ChatOpenAI(
    api_key=openrouter_api_key,
    base_url="https://openrouter.ai/api/v1",
    model=model_name,
    temperature=0,
)

# 3. Configurar Herramientas (Tools)
search_tool = TavilySearchResults(
    tavily_api_key=tavily_api_key,
    max_results=3
)

# Aquí agregaremos luego la herramienta del Dashboard
tools = [search_tool] 

# 4. Inicializar el Agente
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    handle_parsing_errors=True
)

# --- ESTO ES LO NUEVO: La función para que main.py la use ---
def get_agent_response(user_message: str):
    """
    Esta función recibe el mensaje del usuario, se lo pasa al agente
    y devuelve la respuesta final.
    """
    try:
        response = agent.run(user_message)
        return response
    except Exception as e:
        return f"Ocurrió un error al procesar tu solicitud: {str(e)}"