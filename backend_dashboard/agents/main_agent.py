import os
import logging
from datetime import datetime
import locale
import operator
from typing import List, Any, TypedDict, Annotated

try: locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except: pass

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain.memory import ConversationSummaryBufferMemory
from langchain_community.chat_message_histories import ChatMessageHistory

from tools.general import get_search_tool
from tools.email import crear_borrador_email
from tools.database import consultar_actas_reuniones, consultar_biblioteca_documentos
from tools.dashboard import consultar_calendario_ministerio, consultar_calendario_cliente
from tools.analysis import analista_de_datos_cliente
from tools.actions import agendar_reunion_oficial, enviar_email_real

logger = logging.getLogger(__name__)

llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash-001", temperature=0, max_retries=2)

def get_memory_aware_history(history_list):
    chat_history = ChatMessageHistory()
    for msg in (history_list[:-1] if history_list else []):
        txt = getattr(msg, 'text', msg.get('text', ''))
        sender = getattr(msg, 'sender', msg.get('sender', ''))
        if sender == 'user': chat_history.add_user_message(txt)
        else: chat_history.add_ai_message(txt)
    
    mem = ConversationSummaryBufferMemory(llm=llm, chat_memory=chat_history, max_token_limit=1500, return_messages=True, memory_key="chat_history")
    return mem.load_memory_variables({})["chat_history"]

# --- PROMPT REFORZADO ---
sys_prompt = f"""Eres Pitu, Asistente de Gestión del MinCYT. 
Hoy es {datetime.now().strftime("%d/%m/%Y")}.

### TUS HERRAMIENTAS Y CUÁNDO USARLAS:

1. **analista_de_datos_cliente** (LA MÁS IMPORTANTE):
   - Úsala SIEMPRE que pregunten por **EXPEDIENTES (EE)**, **COSTOS**, **LUGARES**, **FUNCIONARIOS** o **ESTADOS**.
   - Ejemplo: "¿Cuál es el expediente de Punta Cana?" -> USA ESTA HERRAMIENTA.
   - Ejemplo: "¿Quién viajo a Viena?" -> USA ESTA HERRAMIENTA.

2. **consultar_calendario_ministerio**:
   - Solo para agenda protocolar del Ministro.

3. **consultar_biblioteca_documentos**:
   - Solo si piden buscar dentro de un PDF (Resoluciones, Decretos).

¡No respondas "no sé" sin haber usado la herramienta `analista_de_datos_cliente` primero!
"""

tools = [analista_de_datos_cliente, consultar_calendario_ministerio, consultar_calendario_cliente, consultar_biblioteca_documentos, consultar_actas_reuniones, crear_borrador_email, get_search_tool(), agendar_reunion_oficial, enviar_email_real]
llm_with_tools = llm.bind_tools(tools)

class State(TypedDict): messages: Annotated[List[BaseMessage], operator.add]
def call_model(s): return {"messages": [llm_with_tools.invoke(s['messages'])]}
def route(s): return "tools" if s['messages'][-1].tool_calls else END

wf = StateGraph(State)
wf.add_node("agent", call_model)
wf.add_node("tools", ToolNode(tools))
wf.set_entry_point("agent")
wf.add_conditional_edges("agent", route, {"tools": "tools", END: END})
wf.add_edge("tools", "agent")
app = wf.compile()

def get_agent_response(msg, hist=[]):
    try:
        res = app.invoke({"messages": [SystemMessage(content=sys_prompt)] + get_memory_aware_history(hist) + [HumanMessage(content=msg)]}, config={"recursion_limit": 20})
        return res["messages"][-1].content
    except Exception as e:
        logger.error(f"Error: {e}")
        return "Error técnico momentáneo."