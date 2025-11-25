from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor
from langchain.tools import Tool
from langchain.hub import hub

from core.config import settings
from tools.general import get_search_tool
from tools.dashboard import consultar_calendario


llm = ChatOpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model=settings.MODEL_NAME,
    temperature=0,
)

# Cargamos prompt recomendado
prompt = hub.pull("hwchase17/openai-functions-agent")

# Herramientas
search_tool = get_search_tool()
tools = [search_tool, consultar_calendario]

# Creamos AgentExecutor con el llm y herramientas
agent = AgentExecutor.from_agent_and_tools(
    agent=prompt,  # Usa el prompt como base del agente
    tools=tools,
    llm=llm,
    verbose=True
)


def get_agent_response(user_message: str):
    try:
        response = agent.invoke({"input": user_message})
        return response["output"]
    except Exception as e:
        return f"Ocurrió un error en el agente: {str(e)}"
