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

# --- IMPORTS DE LANGGRAPH (NUEVA ARQUITECTURA) ---
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
# [CORRECCIÓN 1: Importar nuevas acciones de escritura]
from tools.actions import agendar_reunion_oficial, enviar_email_real

logger = logging.getLogger(__name__)

# 1. Configuración del Modelo Principal
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0,
    max_retries=2,
)

fecha_actual = datetime.now().strftime("%A %d de %B de %Y")

# --- FUNCIÓN DE MEMORIA INTELIGENTE ---
def get_memory_aware_history(history_list: List[Any]) -> List[BaseMessage]:
    """
    Transforma la lista cruda de mensajes en una memoria optimizada.
    Si el historial es largo, RESUME los mensajes antiguos y mantiene los recientes.
    """
    if not history_list:
        return []

    # 1. Reconstruir el historial en formato LangChain
    chat_history_obj = ChatMessageHistory()
    
    # Excluimos el último (input actual) para no duplicarlo si viene en la lista
    history_to_process = history_list[:-1] 

    for msg in history_to_process:
        # Normalización de formato (dict vs objeto Pydantic)
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

    # 2. Aplicar SummaryBufferMemory
    memory = ConversationSummaryBufferMemory(
        llm=llm,
        chat_memory=chat_history_obj,
        max_token_limit=1000, 
        return_messages=True,
        memory_key="chat_history"
    )

    # 3. Extraer los mensajes procesados
    final_history = memory.load_memory_variables({})["chat_history"]
    
    return final_history

# --- SYSTEM PROMPT ---
# [CORRECCIÓN 2: Actualizar instrucciones con capacidades de acción]
system_instructions = f"""Eres Pitu, el Asistente Inteligente del MinCYT. 
HOY ES: {fecha_actual}.

TU MISIÓN: Responder consultas sobre la gestión del Ministerio con precisión absoluta y ejecutar acciones administrativas cuando se solicite.

### 1. PROTOCOLO DE SELECCIÓN DE FUENTES (JERARQUÍA):

**A. DINERO / LOGÍSTICA / GESTIÓN INTERNA:**
   - Usa: `analista_de_datos_cliente` (OBLIGATORIO si piden totales, sumas o filtros complejos).
   - *Nota:* Si piden listados simples sin cálculo ("muéstrame los viajes"), usa `consultar_calendario_cliente`.

**B. AGENDA OFICIAL / ACTOS PÚBLICOS:**
   - Usa: `consultar_calendario_ministerio`.

**C. DOCUMENTOS / RESOLUCIONES (FALLBACK):**
   - Si no está en las agendas, usa: `consultar_biblioteca_documentos`.
   - REGLA DE CITA: Si usas esta herramienta, termina tu frase con: [Fuente: Nombre del Documento].

**D. MEMORIA DE REUNIONES:**
   - Usa: `consultar_actas_reuniones`.

### 2. REGLAS DE ORO:
1. **CÁLCULOS:** NUNCA sumes mentalmente los datos de las listas. Usa SIEMPRE `analista_de_datos_cliente` para matemáticas.
2. **HONESTIDAD:** Si no hay datos en ninguna fuente, dilo claramente.
3. **MEMORIA:** Tienes acceso a un resumen de la conversación anterior.

### 3. ACCIONES DE ESCRITURA (¡CUIDADO!):
- Para **agendar reuniones**, usa `agendar_reunion_oficial`. Pide confirmación de fecha y hora antes de ejecutar.
- Para **enviar correos**, si el usuario dice "envíalo" o "mándalo", usa `enviar_email_real`. Si solo dice "redacta" o "prepara", usa `crear_borrador_email`.
"""

# --- CONFIGURACIÓN DE HERRAMIENTAS ---
# [CORRECCIÓN 3: Agregar las nuevas herramientas a la lista]
tools = [
    analista_de_datos_cliente,
    consultar_calendario_ministerio,
    consultar_calendario_cliente,
    consultar_biblioteca_documentos,
    consultar_actas_reuniones,
    crear_borrador_email,
    get_search_tool(),
    # Nuevas capacidades Fase 2
    agendar_reunion_oficial,
    enviar_email_real
]

# Vinculamos las herramientas al LLM para que sepa cuáles puede llamar
llm_with_tools = llm.bind_tools(tools)

# --- DEFINICIÓN DEL GRAFO (LANGGRAPH) ---

# 1. Definir el Estado del Agente
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]

# 2. Nodo: El Agente (Cerebro)
def call_model(state: AgentState):
    messages = state['messages']
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# 3. Nodo: Ejecutor de Herramientas
tool_node = ToolNode(tools)

# 4. Lógica de enrutamiento
def should_continue(state: AgentState):
    last_message = state['messages'][-1]
    if last_message.tool_calls:
        return "tools"
    return END

# 5. Construcción del Grafo
workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.set_entry_point("agent")

workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        END: END
    }
)

workflow.add_edge("tools", "agent")

app_graph = workflow.compile()

# --- FUNCIÓN DE RESPUESTA PRINCIPAL ---

def get_agent_response(user_message: str, chat_history: List[Any] = []):
    try:
        logger.info(f"🤖 Pitu Procesando (Graph+Actions): {user_message}")
        
        # 1. Preparar memoria e input
        history_objects = get_memory_aware_history(chat_history)
        
        # Debug memoria
        if len(history_objects) > 0 and isinstance(history_objects[0], SystemMessage):
            logger.info(f"🧠 Memoria comprimida activa. Resumen: {history_objects[0].content[:60]}...")

        # 2. Construir la lista inicial de mensajes para el grafo
        input_messages = [SystemMessage(content=system_instructions)] + history_objects + [HumanMessage(content=user_message)]
        
        # 3. Ejecutar el Grafo
        result = app_graph.invoke(
            {"messages": input_messages},
            config={"recursion_limit": 15}
        )
        
        # 4. Extraer la respuesta final
        last_message = result["messages"][-1]
        return last_message.content

    except Exception as e:
        logger.error(f"❌ Error Crítico en Agente (Graph): {str(e)}", exc_info=True)
        return f"Lo siento, ocurrió un error técnico en el procesamiento cognitivo: {str(e)}"