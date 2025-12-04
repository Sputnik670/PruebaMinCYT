import os
import logging
from datetime import datetime
import locale
from typing import List, Any, TypedDict, Annotated
import operator

# Configuración de Locale
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    pass

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# --- IMPORTS DE LANGGRAPH ---
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

# --- IMPORTS PARA MEMORIA ---
from langchain.memory import ConversationSummaryBufferMemory
from langchain_community.chat_message_histories import ChatMessageHistory

# --- IMPORTS DE HERRAMIENTAS ---
from tools.general import get_search_tool
from tools.email import crear_borrador_email
from tools.database import consultar_actas_reuniones, consultar_biblioteca_documentos
from tools.dashboard import (
    consultar_calendario_ministerio, 
    consultar_calendario_cliente
)
from tools.analysis import analista_de_datos_cliente
from tools.actions import agendar_reunion_oficial, enviar_email_real

logger = logging.getLogger(__name__)

# 1. Configuración del Modelo Principal (CORREGIDO a 1.5 Flash)
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash", # <--- VERSIÓN ESTABLE Y RÁPIDA
    temperature=0,
    max_retries=2,
)

fecha_actual = datetime.now().strftime("%A %d de %B de %Y")

# --- FUNCIÓN DE MEMORIA INTELIGENTE ---
def get_memory_aware_history(history_list: List[Any]) -> List[BaseMessage]:
    """
    Transforma la lista cruda de mensajes en una memoria optimizada.
    """
    if not history_list:
        return []

    chat_history_obj = ChatMessageHistory()
    history_to_process = history_list[:-1] 

    for msg in history_to_process:
        if isinstance(msg, dict):
            sender = msg.get('sender')
            text = msg.get('text', '')
        else:
            sender = getattr(msg, 'sender', None)
            text = getattr(msg, 'text', '')

        if sender == 'user':
            chat_history_obj.add_user_message(text)
        elif sender in ['bot', 'assistant']:
            chat_history_obj.add_ai_message(text)

    memory = ConversationSummaryBufferMemory(
        llm=llm,
        chat_memory=chat_history_obj,
        max_token_limit=1500, # Aumentado para retener más contexto numérico
        return_messages=True,
        memory_key="chat_history"
    )

    return memory.load_memory_variables({})["chat_history"]

# --- SYSTEM PROMPT AVANZADO (Cadena de Pensamiento) ---
system_instructions = f"""Eres Pitu, el Asistente de Alta Gerencia del MinCYT. 
FECHA ACTUAL: {fecha_actual}.

TU OBJETIVO: Resolver consultas complejas sobre gestión, presupuesto y agenda mediante el uso estratégico de herramientas.

### 🧠 ESTRATEGIA DE RAZONAMIENTO (Chain of Thought):
Antes de responder, PIENSA paso a paso:
1. **¿Qué me están pidiendo?** (Dato puntual, cálculo matemático, redacción o acción).
2. **¿Tengo el dato en mi memoria?** Si no, ¿qué herramienta lo tiene?
3. **¿Es un cálculo?** -> DELEGO AL `analista_de_datos_cliente`. NO calculo yo.
4. **¿Es una acción?** -> Confirmo detalles antes de ejecutar `agendar` o `enviar`.

### 🛠️ SELECCIÓN DE HERRAMIENTAS:

- **analista_de_datos_cliente**: TU MEJOR AMIGO. Úsalo para:
  - "Gastos totales de viajes a Córdoba".
  - "Cuántos eventos hubo en Noviembre".
  - "Sumar el presupuesto del área X".
  - *Tip:* Si la pregunta implica números o filtros, úsala.

- **consultar_calendario_ministerio**: Solo para agenda pública/política del Ministro.
- **consultar_calendario_cliente**: Para listados crudos de logística interna (sin cálculos).
- **consultar_biblioteca_documentos**: Para buscar en PDFs subidos (Resoluciones, Informes).
- **consultar_actas_reuniones**: Para saber qué se habló en reuniones pasadas.

### 🚨 REGLAS DE SEGURIDAD Y ESTILO:
1. **Cero Alucinación Numérica:** Si el analista no devuelve un número, di "No tengo el dato exacto", no inventes.
2. **Citas:** Si sacas info de un documento, indica: [Fuente: Documento X].
3. **Acciones:** Para agendar o enviar emails reales, pide confirmación explícita ("¿Confirma que agendo para el martes a las 15hs?").

¡Comencemos! Analiza la consulta del usuario."""

# --- CONFIGURACIÓN DE HERRAMIENTAS ---
tools = [
    analista_de_datos_cliente,
    consultar_calendario_ministerio,
    consultar_calendario_cliente,
    consultar_biblioteca_documentos,
    consultar_actas_reuniones,
    crear_borrador_email,
    get_search_tool(),
    agendar_reunion_oficial,
    enviar_email_real
]

llm_with_tools = llm.bind_tools(tools)

# --- DEFINICIÓN DEL GRAFO ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

def call_model(state: AgentState):
    messages = state['messages']
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

tool_node = ToolNode(tools)

def should_continue(state: AgentState):
    last_message = state['messages'][-1]
    if last_message.tool_calls:
        return "tools"
    return END

workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
workflow.add_edge("tools", "agent")

app_graph = workflow.compile()

# --- FUNCIÓN DE RESPUESTA PRINCIPAL ---
def get_agent_response(user_message: str, chat_history: List[Any] = []):
    try:
        logger.info(f"🤖 Pitu Pensando: {user_message}")
        history_objects = get_memory_aware_history(chat_history)
        input_messages = [SystemMessage(content=system_instructions)] + history_objects + [HumanMessage(content=user_message)]
        
        result = app_graph.invoke(
            {"messages": input_messages},
            config={"recursion_limit": 20} # Aumentado para permitir razonamientos largos
        )
        return result["messages"][-1].content

    except Exception as e:
        logger.error(f"❌ Error en Agente: {str(e)}", exc_info=True)
        return f"Tuve un problema técnico procesando eso. ¿Podrías reformularlo? (Error: {str(e)})"