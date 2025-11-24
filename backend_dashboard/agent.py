# Archivo: backend/agent.py
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
# CORRECCION AQUI: Importamos directamente desde langchain_hub
from langchain_community.hub import pull

from langchain.agents import AgentExecutor, create_structured_chat_agent
from langchain_community.tools.tavily_search import TavilySearchResults

load_dotenv()

openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
tavily_api_key = os.getenv("TAVILY_API_KEY")
model_name = os.getenv("MODEL_NAME", "google/gemini-flash-1.5")

if not openrouter_api_key:
    raise ValueError("Falta la OPENROUTER_API_KEY en las variables de entorno")

llm = ChatOpenAI(
    api_key=openrouter_api_key,
    base_url="https://openrouter.ai/api/v1",
    model=model_name,
    temperature=0,
)

search_tool = TavilySearchResults(
    tavily_api_key=tavily_api_key,
    max_results=3
)
tools = [search_tool]

# CORRECCION AQUI: Usamos 'pull' directamente, sin 'hub.' antes
prompt = pull("hwchase17/structured-chat-agent")

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