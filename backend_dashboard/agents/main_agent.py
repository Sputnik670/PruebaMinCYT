import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

# Imports de herramientas
from tools.general import get_search_tool
from tools.dashboard import consultar_calendario
from tools.email import crear_borrador_email
from tools.docs import consultar_documento
# IMPORTANTE: Importamos la herramienta de memoria
from tools.database import consultar_base_de_datos_actas

# 1. Configuración del Modelo
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    max_retries=2,
)

# 2. Prompt con instrucciones de Memoria
prompt = ChatPromptTemplate.from_messages([
    ("system", "Eres el asistente virtual del MinCYT. "
               "Tienes acceso a herramientas para buscar en internet, ver el calendario, "
               "leer documentos PDF subidos y CONSULTAR ACTAS DE REUNIONES en la base de datos. "
               "Si te preguntan por temas pasados o 'qué se habló', USA la herramienta 'consultar_base_de_datos_actas'."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# 3. Lista de Herramientas (Asegúrate de que estén todas aquí)
tools = [
    get_search_tool(), 
    consultar_calendario, 
    crear_borrador_email, 
    consultar_documento, 
    consultar_base_de_datos_actas # <--- ¡Conectada!
]

# 4. Crear Agente
agent_runnable = create_tool_calling_agent(llm, tools, prompt)

agent = AgentExecutor(
    agent=agent_runnable,
    tools=tools,
    verbose=True,
    max_iterations=10,
    max_execution_time=30,
    handle_parsing_errors=True
)

def get_agent_response(user_message: str):
    try:
        print(f"🤖 IA Procesando: {user_message}")
        response = agent.invoke({"input": user_message})
        return response["output"]
    except Exception as e:
        print(f"❌ Error Agente: {str(e)}")
        return "Lo siento, tuve un problema técnico interno."