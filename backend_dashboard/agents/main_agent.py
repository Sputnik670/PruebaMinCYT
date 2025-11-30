import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

# Imports de herramientas
from tools.general import get_search_tool
from tools.email import crear_borrador_email

# IMPORTANTE: Importamos las herramientas de memoria y las NUEVAS de calendario
from tools.database import consultar_actas_reuniones, consultar_biblioteca_documentos
from tools.dashboard import (
    consultar_calendario_ministerio, 
    consultar_calendario_cliente
)

# 1. Configuración del Modelo
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    max_retries=2,
)

# 2. Prompt con instrucciones de Memoria, Biblioteca y DOBLE CALENDARIO
prompt = ChatPromptTemplate.from_messages([
    ("system", "Eres Pitu, el asistente experto del MinCYT. \n\n"
               "**FUENTES DE INFORMACIÓN:**\n"
               "1. **Agenda Ministerio (Pública):** Usa 'consultar_calendario_ministerio' para actos de gobierno, visitas oficiales o agenda del Ministro.\n"
               "2. **Agenda Interna (Cliente):** Usa 'consultar_calendario_cliente' para reuniones de equipo, privados, o cuando el usuario diga 'mi agenda' o 'mis reuniones'.\n"
               "3. **Memoria de Reuniones (Actas):** Usa 'consultar_actas_reuniones' si preguntan 'qué se habló' o 'qué decidimos' en el pasado.\n"
               "4. **Biblioteca (Archivos):** Usa 'consultar_biblioteca_documentos' para datos técnicos, presupuestos o PDFs subidos.\n\n"
               "**IMPORTANTE:** Si te preguntan por conflictos de horario, consulta AMBAS agendas antes de responder."
    ),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# 3. Lista de Herramientas Actualizada
tools = [
    get_search_tool(), 
    consultar_calendario_ministerio, # <--- Ojo Izquierdo (Ministerio)
    consultar_calendario_cliente,    # <--- Ojo Derecho (Cliente)
    crear_borrador_email, 
    consultar_actas_reuniones,
    consultar_biblioteca_documentos
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
        print(f"🤖 Pitu Procesando: {user_message}")
        response = agent.invoke({"input": user_message})
        return response["output"]
    except Exception as e:
        print(f"❌ Error Agente: {str(e)}")
        return "Lo siento, estoy teniendo problemas técnicos para procesar tu solicitud."