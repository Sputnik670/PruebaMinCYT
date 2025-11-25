from langchain_openai import ChatOpenAI
from langchain import hub
from langchain.agents import AgentExecutor, create_structured_chat_agent

from core.config import settings
# IMPORTAMOS LAS DOS HERRAMIENTAS
from tools.general import get_search_tool
from tools.dashboard import consultar_calendario  # <--- NUEVA IMPORTACIÓN

llm = ChatOpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model=settings.MODEL_NAME,
    temperature=0,
)

# 1. Configuramos Tavily (Internet)
search_tool = get_search_tool()

# 2. Preparamos la lista de herramientas
# ¡AQUÍ ESTÁ LA CLAVE! Le damos ambas al agente.
tools = [search_tool, consultar_calendario]

prompt = hub.pull("hwchase17/structured-chat-agent")

agent = create_structured_chat_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    verbose=True, 
    handle_parsing_errors=True
)

def get_agent_response(user_message: str):
    try:
        response = agent_executor.invoke({"input": user_message})
        return response["output"]
    except Exception as e:
        return f"Ocurrió un error en el agente: {str(e)}"