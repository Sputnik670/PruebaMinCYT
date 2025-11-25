from langchain_openai import ChatOpenAI
from langchain_hub import pull
from langchain.agents import AgentExecutor, create_structured_chat_agent

# --- AQUÍ ESTÁ LA MAGIA ---
# Importamos la configuración y las herramientas desde los otros módulos
from core.config import settings
from tools.general import get_search_tool

# 1. Configurar el LLM (Cerebro)
# Usamos las variables que definiste en core/config.py
llm = ChatOpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model=settings.MODEL_NAME,
    temperature=0,
)

# 2. Cargar Herramientas (Manos)
# Obtenemos la herramienta de Tavily desde tools/general.py
search_tool = get_search_tool()

# Lista de herramientas (aquí agregaremos el Dashboard y PDFs luego)
tools = [search_tool]

# 3. Crear el Agente (Personalidad)
# Descargamos las instrucciones base desde el Hub
prompt = pull("hwchase17/structured-chat-agent")

agent = create_structured_chat_agent(llm, tools, prompt)

# 4. Crear el Ejecutor (Cuerpo)
agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    verbose=True, 
    handle_parsing_errors=True
)

# --- Función pública para usar desde main.py ---
def get_agent_response(user_message: str):
    """
    Recibe el mensaje del usuario y devuelve la respuesta del agente.
    """
    try:
        response = agent_executor.invoke({"input": user_message})
        return response["output"]
    except Exception as e:
        return f"Ocurrió un error en el agente: {str(e)}"