import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain.tools import Tool

from tools.general import get_search_tool
from tools.dashboard import consultar_calendario
from tools.email import crear_borrador_email

# 1. Configuración del Modelo (Gemini 1.5 Flash)
# Requiere que la clave GOOGLE_API_KEY esté vinculada a una cuenta con facturación activa.
llm = ChatGoogleGenerativeAI(
    model="gemini-pro",
    temperature=0,
    max_retries=3, # Aumentamos retries para mayor tolerancia a fallos de red
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
    handle_parsing_errors=True, # Gemini a veces es hablador, esto lo corrige
    max_iterations=5
)

def get_agent_response(user_message: str):
    try:
        print(f"🤖 Gemini Pregunta: {user_message}")
        response = agent.invoke({"input": user_message})
        return response["output"]
    except Exception as e:
        print(f"❌ Error Gemini: {str(e)}")
        return "Lo siento, tuve un problema procesando tu solicitud. Intenta reformular la pregunta."