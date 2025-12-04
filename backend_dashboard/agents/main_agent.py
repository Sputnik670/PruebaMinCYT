import os
import logging
from datetime import datetime
import locale
import operator
from typing import List, Any, TypedDict, Annotated

# Configuración de locale para fechas (intento)
try: locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except: pass

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain.memory import ConversationSummaryBufferMemory
from langchain_community.chat_message_histories import ChatMessageHistory

# Importación de herramientas
from tools.general import get_search_tool
from tools.email import crear_borrador_email
from tools.database import consultar_actas_reuniones, consultar_biblioteca_documentos
from tools.dashboard import consultar_calendario_ministerio, consultar_calendario_cliente
from tools.analysis import analista_de_datos_cliente
from tools.actions import agendar_reunion_oficial, enviar_email_real

logger = logging.getLogger(__name__)

# Modelo: Usamos Flash con temperatura 0 para precisión en instrucciones
llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash-001", temperature=0, max_retries=2)

def get_memory_aware_history(history_list):
    """
    Recupera el historial de chat de forma segura, manejando tanto
    Diccionarios (base de datos) como Objetos Pydantic (frontend).
    """
    chat_history = ChatMessageHistory()
    
    # Procesamos todo menos el último mensaje (que es el actual)
    for msg in (history_list[:-1] if history_list else []):
        # --- CORRECCIÓN CRÍTICA AQUÍ ---
        # Verificamos si es diccionario antes de usar .get()
        if isinstance(msg, dict):
            txt = msg.get('text', '')
            sender = msg.get('sender', '')
        else:
            # Si es objeto (Pydantic), usamos getattr
            txt = getattr(msg, 'text', '')
            sender = getattr(msg, 'sender', '')
        # -------------------------------

        if sender == 'user': 
            chat_history.add_user_message(txt)
        else: 
            chat_history.add_ai_message(txt)
    
    mem = ConversationSummaryBufferMemory(
        llm=llm, 
        chat_memory=chat_history, 
        max_token_limit=1500, 
        return_messages=True, 
        memory_key="chat_history"
    )
    return mem.load_memory_variables({})["chat_history"]

# --- PROMPT REFORZADO (MODO ESTRICTO DE DATOS) ---
sys_prompt = f"""Eres Pitu, Asistente de Gestión Inteligente del MinCYT. 
Hoy es {datetime.now().strftime("%d/%m/%Y")}.

### TU MISIÓN:
Tu único objetivo es consultar la base de datos en tiempo real y dar respuestas precisas basadas en EVIDENCIA.

### REGLAS DE COMPORTAMIENTO (STRICT MODE):
1. **PREGUNTAS DE DATOS = HERRAMIENTA `analista_de_datos_cliente`**:
   - Si preguntan: "¿Cuánto se gastó?", "¿Quién viajó?", "¿Estado del expediente?", "¿Viajes a Viena?", "¿Costos totales?".
   - **DEBES** usar la herramienta `analista_de_datos_cliente`.
   - NO respondas "no sé" ni "no tengo esa información" sin antes haber ejecutado esta herramienta.

2. **AGENDA OFICIAL**:
   - Solo usa `consultar_calendario_ministerio` para preguntas sobre la agenda protocolar pública del Ministro.

3. **NO ALUCINES**:
   - Si la herramienta devuelve un DataFrame vacío o un error, dilo honestamente: "No encontré registros con ese criterio en la base de datos".

4. **FORMATO**:
   - Si hay múltiples resultados, preséntalos en una lista limpia.
   - Si es un monto de dinero, aclara siempre la moneda (USD, EUR, ARS).

¡Confía en tu herramienta de análisis, ella tiene los datos matemáticos precisos!
"""

# Lista de herramientas
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

# --- GRAFO LANGGRAPH ---
class State(TypedDict): messages: Annotated[List[BaseMessage], operator.add]

def call_model(s): 
    return {"messages": [llm_with_tools.invoke(s['messages'])]}

def route(s): 
    return "tools" if s['messages'][-1].tool_calls else END

wf = StateGraph(State)
wf.add_node("agent", call_model)
wf.add_node("tools", ToolNode(tools))
wf.set_entry_point("agent")
wf.add_conditional_edges("agent", route, {"tools": "tools", END: END})
wf.add_edge("tools", "agent")
app = wf.compile()

def get_agent_response(msg, hist=[]):
    try:
        res = app.invoke(
            {"messages": [SystemMessage(content=sys_prompt)] + get_memory_aware_history(hist) + [HumanMessage(content=msg)]}, 
            config={"recursion_limit": 20}
        )
        return res["messages"][-1].content
    except Exception as e:
        logger.error(f"Error en agente: {e}")
        return "Tuve un error técnico momentáneo procesando tu solicitud."