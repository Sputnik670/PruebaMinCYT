import os
import logging
from datetime import datetime
import locale
from typing import List, Any

try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    pass

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

# Imports de herramientas
from tools.general import get_search_tool
from tools.email import crear_borrador_email
from tools.database import consultar_actas_reuniones, consultar_biblioteca_documentos
from tools.dashboard import (
    consultar_calendario_ministerio, 
    consultar_calendario_cliente
)
from tools.analysis import analista_de_datos_cliente 

logger = logging.getLogger(__name__)

# 1. Configuración del Modelo
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    max_retries=2,
)

fecha_actual = datetime.now().strftime("%A %d de %B de %Y")

# --- FUNCIÓN CORREGIDA PARA MEMORIA REAL ---
def format_chat_history(history: List[Any]) -> List[Any]:
    """
    Convierte el historial en objetos de mensaje de LangChain (HumanMessage/AIMessage).
    Esto mejora drásticamente la capacidad del modelo para recordar el contexto.
    """
    if not history:
        return []
    
    formatted_messages = []
    
    # Excluimos el último porque LangChain ya recibe el 'input' actual por separado
    history_to_process = history[:-1] 

    for msg in history_to_process:
        # Detectar si es dict o objeto Pydantic
        if isinstance(msg, dict):
            sender = msg.get('sender')
            text = msg.get('text', '')
        else:
            sender = getattr(msg, 'sender', None)
            text = getattr(msg, 'text', '')

        if sender == 'user':
            formatted_messages.append(HumanMessage(content=text))
        else:
            formatted_messages.append(AIMessage(content=text))
            
    return formatted_messages

# --- CONTEXTO Y PROMPT MEJORADO (Lógica Robusta) ---
contexto_datos = """
ESTRUCTURA DE DATOS Y FUENTES:
El sistema maneja dos fuentes de verdad distintas. Debes elegir la correcta según la intención del usuario:

1. **AGENDA PÚBLICA / MINISTERIO (Oficial):**
   - Contiene actos oficiales, reuniones públicas y ceremonias.
   - DATOS: Fechas, Horas, Lugares, Títulos de eventos.
   - **NO** tiene información de costos, choferes, ni estados administrativos.

2. **GESTIÓN INTERNA / CLIENTE (Operativa):**
   - Contiene la logística de viajes, traslados y comisiones de servicio.
   - DATOS: Institución, Pasajeros, **COSTOS**, **PRESUPUESTOS**, Nros de Expediente (EE), Estados (Rendición).
   - Si la pregunta implica dinero, logística o trámites, SIEMPRE es esta fuente.
"""

system_instructions = f"""Eres Pitu, el Asistente del MinCYT. HOY ES: {fecha_actual}.

{contexto_datos}

PRINCIPIOS DE RAZONAMIENTO:
- **Análisis Financiero:** Para sumar costos, presupuestos o filtrar por gastos, la herramienta `analista_de_datos_cliente` es la única capaz de hacer matemática precisa. Úsala preferentemente sobre la lectura simple.
- **Consultas Híbridas:** Si te piden "listado y costos", usa las herramientas de Gestión Interna (Cliente) o el analista, ya que la Agenda Pública no tendrá el dato del costo y fallarás si la consultas.
- **Precisión:** Si usas el analista de datos, confía ciegamente en su resultado numérico.
"""

# --- DEFINICIÓN DEL PROMPT TEMPLATE ---
prompt = ChatPromptTemplate.from_messages([
    ("system", system_instructions),
    MessagesPlaceholder(variable_name="chat_history"), # Inyección de memoria real
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

tools = [
    analista_de_datos_cliente,       
    get_search_tool(), 
    consultar_calendario_ministerio, 
    consultar_calendario_cliente,    
    crear_borrador_email, 
    consultar_actas_reuniones,
    consultar_biblioteca_documentos
]

agent_runnable = create_tool_calling_agent(llm, tools, prompt)

agent = AgentExecutor(
    agent=agent_runnable,
    tools=tools,
    verbose=True,
    max_iterations=10, 
    handle_parsing_errors=True
)

def get_agent_response(user_message: str, chat_history: List[Any] = []):
    try:
        logger.info(f"🤖 Pitu Procesando: {user_message}")
        
        # Convertimos historial a objetos
        history_objects = format_chat_history(chat_history)
        
        response = agent.invoke({
            "input": user_message,
            "chat_history": history_objects 
        })
        return response["output"]
    except Exception as e:
        logger.error(f"❌ Error Agente: {str(e)}", exc_info=True)
        return f"Error técnico: {str(e)}"