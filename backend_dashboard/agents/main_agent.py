import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

# Imports de herramientas
from tools.general import get_search_tool
from tools.dashboard import consultar_calendario
from tools.email import crear_borrador_email
# from tools.docs import consultar_documento # (Opcional: Ya no es estrictamente necesaria si usamos la biblioteca)

# IMPORTANTE: Importamos las herramientas de memoria (Actas y Biblioteca)
# Asegúrate de que estos nombres coincidan con los @tool en tools/database.py
from tools.database import consultar_actas_reuniones, consultar_biblioteca_documentos

# 1. Configuración del Modelo
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    max_retries=2,
)

# 2. Prompt con instrucciones de Memoria y Biblioteca
# Aquí le enseñamos a Pitu a distinguir entre "lo que se habló" (Actas) y "lo que está escrito" (Biblioteca)
prompt = ChatPromptTemplate.from_messages([
    ("system", "Eres Pitu, el asistente experto del MinCYT. "
               "Tienes acceso a dos fuentes de memoria principales: \n"
               "1. **Memoria de Reuniones (Actas):** Usa la herramienta 'consultar_actas_reuniones' si el usuario pregunta 'qué se habló', 'qué decidimos', o sobre el historial de conversaciones pasadas.\n"
               "2. **Biblioteca de Documentos (Archivos):** Usa la herramienta 'consultar_biblioteca_documentos' si el usuario busca datos específicos, presupuestos, cronogramas (ej: 2026), tablas o información técnica contenida en PDFs o Excels subidos.\n"
               "IMPORTANTE: Cuando respondas usando la biblioteca, intenta citar el nombre del archivo de donde sacaste el dato."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# 3. Lista de Herramientas
tools = [
    get_search_tool(), 
    consultar_calendario, 
    crear_borrador_email, 
    # consultar_documento, # Dejamos esta comentada/fuera por ahora para priorizar la biblioteca
    consultar_actas_reuniones,      # <--- Busca en actas_reunion
    consultar_biblioteca_documentos # <--- Busca en libreria_documentos (Vectores)
]

# 4. Crear Agente
agent_runnable = create_tool_calling_agent(llm, tools, prompt)

agent = AgentExecutor(
    agent=agent_runnable,
    tools=tools,
    verbose=True, # Esto te permitirá ver en la consola qué herramienta elige usar
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
        return "Lo siento, estoy teniendo problemas para acceder a mi biblioteca de documentos en este momento."