import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_react_agent
from langchain.agents.agent import AgentExecutor
from langchain_core.prompts import PromptTemplate
# Eliminamos imports no usados para limpiar

from tools.general import get_search_tool
from tools.dashboard import consultar_calendario
from tools.email import crear_borrador_email

# 1. Configuración del Modelo (Gemini 1.5 Flash)
# Usamos el nombre canónico completo para evitar ambigüedades
# ... imports ...

# 1. Configuración del Modelo (Gemini 1.5 Flash)
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0,
    max_retries=2,
    # ELIMINAMOS transport="rest" para dejar que la librería use su defecto optimizado
)


# 2. Prompt ReAct (Optimizado para Gemini)
template = '''Responde las preguntas del usuario usando las siguientes herramientas.

{tools}

Usa el siguiente formato EXACTO:

Pregunta: la pregunta de entrada que debes responder
Pensamiento: siempre debes pensar qué hacer
Acción: la acción a tomar, debe ser una de [{tool_names}]
Entrada de Acción: la entrada para la acción (sin comillas extrañas)
Observación: el resultado de la acción
... (este Pensamiento/Acción/Entrada de Acción/Observación se puede repetir)
Pensamiento: ahora sé la respuesta final
Respuesta Final: la respuesta final a la pregunta de entrada original

¡Comienza!

Pregunta: {input}
Pensamiento:{agent_scratchpad}'''

prompt = PromptTemplate.from_template(template)

# 3. Herramientas
tools = [get_search_tool(), consultar_calendario, crear_borrador_email]

# 4. Crear Agente
agent_runnable = create_react_agent(llm, tools, prompt)

agent = AgentExecutor(
    agent=agent_runnable,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=5
)

def get_agent_response(user_message: str):
    try:
        print(f"🤖 Gemini Pregunta: {user_message}")
        response = agent.invoke({"input": user_message})
        return response["output"]
    except Exception as e:
        print(f"❌ Error Gemini: {str(e)}")
        return f"Lo siento, ocurrió un error interno: {str(e)}"