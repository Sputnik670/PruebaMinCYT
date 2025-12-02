import os
import logging
from datetime import datetime
import locale
from typing import List, Any

# Configuración de Locale
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    pass

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
# --- NUEVOS IMPORTS PARA MEMORIA (MEJORA 2) ---
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

logger = logging.getLogger(__name__)

# 1. Configuración del Modelo Principal
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    max_retries=2,
)

fecha_actual = datetime.now().strftime("%A %d de %B de %Y")

# --- FUNCIÓN DE MEMORIA INTELIGENTE (MEJORA 2) ---
def get_memory_aware_history(history_list: List[Any]) -> List[Any]:
    """
    Transforma la lista cruda de mensajes en una memoria optimizada.
    Si el historial es largo, RESUME los mensajes antiguos y mantiene los recientes.
    """
    if not history_list:
        return []

    # 1. Reconstruir el historial en formato LangChain
    chat_history_obj = ChatMessageHistory()
    
    # Excluimos el último (input actual) para no duplicarlo
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
    # max_token_limit=1000: Si pasamos de ~1000 tokens, Gemini resume lo antiguo.
    memory = ConversationSummaryBufferMemory(
        llm=llm,
        chat_memory=chat_history_obj,
        max_token_limit=1000, 
        return_messages=True,
        memory_key="chat_history"
    )

    # 3. Extraer los mensajes procesados (SystemMessage con Resumen + Mensajes Recientes)
    final_history = memory.load_memory_variables({})["chat_history"]
    
    return final_history

# --- SYSTEM PROMPT (MEJORA 1: Jerarquía) ---
system_instructions = f"""Eres Pitu, el Asistente Inteligente del MinCYT. 
HOY ES: {fecha_actual}.

TU MISIÓN: Responder consultas sobre la gestión del Ministerio con precisión absoluta.

### 1. PROTOCOLO DE SELECCIÓN DE FUENTES (JERARQUÍA):

**A. DINERO / LOGÍSTICA / GESTIÓN INTERNA:**
   - Usa: `analista_de_datos_cliente` (OBLIGATORIO si piden totales, sumas o filtros complejos).
   - *Nota:* Si piden listados simples sin cálculo ("muéstrame los viajes"), usa `consultar_calendario_cliente`.

**B. AGENDA OFICIAL / ACTOS PÚBLICOS:**
   - Usa: `consultar_calendario_ministerio`.

**C. DOCUMENTOS / RESOLUCIONES (FALLBACK):**
   - Si no está en las agendas, usa: `consultar_biblioteca_documentos`.

**D. MEMORIA DE REUNIONES:**
   - Usa: `consultar_actas_reuniones`.

### 2. REGLAS DE ORO:
1. **CÁLCULOS:** NUNCA sumes mentalmente los datos de las listas. Usa SIEMPRE `analista_de_datos_cliente` para matemáticas.
2. **HONESTIDAD:** Si no hay datos en ninguna fuente (Agenda ni Documentos), dilo claramente.
3. **MEMORIA:** Tienes acceso a un resumen de la conversación anterior. Úsalo si el usuario dice "como te dije antes" o "sobre lo anterior".
"""

# --- DEFINICIÓN DEL AGENTE ---
prompt = ChatPromptTemplate.from_messages([
    ("system", system_instructions),
    MessagesPlaceholder(variable_name="chat_history"), 
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

tools = [
    analista_de_datos_cliente,
    consultar_calendario_ministerio,
    consultar_calendario_cliente,
    consultar_biblioteca_documentos,
    consultar_actas_reuniones,
    crear_borrador_email,
    get_search_tool(),
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
        
        # --- APLICACIÓN DE LA MEJORA 2 ---
        # Usamos la función inteligente en lugar de la simple
        history_objects = get_memory_aware_history(chat_history)
        
        # Debug: Verificar si se generó un resumen
        if len(history_objects) > 0 and isinstance(history_objects[0], SystemMessage):
            logger.info(f"🧠 Memoria comprimida activa. Resumen: {history_objects[0].content[:60]}...")

        response = agent.invoke({
            "input": user_message,
            "chat_history": history_objects 
        })
        
        return response["output"]

    except Exception as e:
        logger.error(f"❌ Error Crítico en Agente: {str(e)}", exc_info=True)
        return f"Lo siento, ocurrió un error técnico: {str(e)}"