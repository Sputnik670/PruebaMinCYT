from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain.tools import Tool

from core.config import settings
from tools.general import get_search_tool
from tools.dashboard import consultar_calendario
from tools.email import crear_borrador_email

# 1. Modelo (Usará el que definas en Render: Llama 3 Free es el recomendado)
llm = ChatOpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model=settings.MODEL_NAME,
    temperature=0,
)

# 2. Prompt ReAct Clásico (El más compatible del mundo)
template = '''Responde las preguntas del usuario lo mejor que puedas. Tienes acceso a las siguientes herramientas:

{tools}

Usa el siguiente formato:

Pregunta: la pregunta de entrada que debes responder
Pensamiento: siempre debes pensar qué hacer
Acción: la acción a tomar, debe ser una de [{tool_names}]
Entrada de Acción: la entrada para la acción
Observación: el resultado de la acción
... (este Pensamiento/Acción/Entrada de Acción/Observación se puede repetir N veces)
Pensamiento: ahora sé la respuesta final
Respuesta Final: la respuesta final a la pregunta de entrada original

¡Comienza!

Pregunta: {input}
Pensamiento:{agent_scratchpad}'''

prompt = PromptTemplate.from_template(template)

# 3. Herramientas
tools = [get_search_tool(), consultar_calendario, crear_borrador_email]

# 4. Crear Agente ReAct
agent_runnable = create_react_agent(llm, tools, prompt)

agent = AgentExecutor(
    agent=agent_runnable,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True, # Auto-corrección de errores
    max_iterations=5            # Evita bucles infinitos
)

def get_agent_response(user_message: str):
    try:
        print(f"🤖 User: {user_message}")
        resp = agent.invoke({"input": user_message})
        return resp["output"]
    except Exception as e:
        print(f"❌ Error Agente: {e}")
        return "Lo siento, mis servicios cognitivos están saturados temporalmente. Intenta de nuevo en unos segundos."