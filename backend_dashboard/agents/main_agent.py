import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

from tools.general import get_search_tool
from tools.dashboard import consultar_calendario
from tools.email import crear_borrador_email
from tools.docs import consultar_documento  # <--- NUEVO IMPORT

# 1. Configuración del Modelo
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    max_retries=2,
)

# 2. Prompt Moderno
prompt = ChatPromptTemplate.from_messages([
    ("system", "Eres el asistente virtual del MinCYT. Tu tono es profesional. "
               "Usa las herramientas disponibles para buscar información actualizada, "
               "consultar el calendario o leer documentos subidos por el usuario. "
               "Si no encuentras información, dilo honestamente."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# 3. Herramientas (AGREGAMOS LA NUEVA)
tools = [get_search_tool(), consultar_calendario, crear_borrador_email, consultar_documento]

# 4. Crear Agente
agent_runnable = create_tool_calling_agent(llm, tools, prompt)

agent = AgentExecutor(
    agent=agent_runnable,
    tools=tools,
    verbose=True,
    max_iterations=15
)

def get_agent_response(user_message: str):
    try:
        print(f"🤖 Gemini Pregunta: {user_message}")
        response = agent.invoke({"input": user_message})
        return response["output"]
    except Exception as e:
        print(f"❌ Error Gemini: {str(e)}")
        return f"Lo siento, ocurrió un error interno: {str(e)}"