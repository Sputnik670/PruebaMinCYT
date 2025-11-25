from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import Tool
from langchain.hub import hub

from core.config import settings
from tools.general import get_search_tool
from tools.dashboard import consultar_calendario

# 1. Configuración del Modelo (Gemini vía OpenRouter)
llm = ChatOpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model=settings.MODEL_NAME,
    temperature=0,
)

# 2. Cargar Prompt base para agentes
prompt = hub.pull("hwchase17/openai-functions-agent")

# 3. Herramientas disponibles
search_tool = get_search_tool()
tools = [search_tool, consultar_calendario]

# 4. Crear el Agente
# Usamos el constructor moderno para evitar advertencias
agent_runnable = create_openai_functions_agent(llm, tools, prompt)

# 5. Ejecutor del Agente (Aquí está el arreglo clave: handle_parsing_errors)
agent = AgentExecutor(
    agent=agent_runnable,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True  # <--- ESTO SOLUCIONA EL 90% DE ERRORES DE CONEXIÓN/FORMATO
)

def get_agent_response(user_message: str):
    try:
        print(f"🤖 Pregunta recibida: {user_message}")
        response = agent.invoke({"input": user_message})
        return response["output"]
    except Exception as e:
        print(f"❌ Error en agente: {str(e)}")
        return "Tuve un problema técnico interno, pero estoy conectado. Intenta preguntar de otra forma."