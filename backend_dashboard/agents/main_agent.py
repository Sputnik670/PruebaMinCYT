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

# --- PROMPT DEL MANAGER (ROUTER / ORQUESTADOR) ---
sys_prompt = f"""Eres el **Director de Operaciones (COO)** del MinCYT. Hoy es {datetime.now().strftime("%d/%m/%Y")}.

TU ROL: No eres un asistente básico. Eres un orquestador de alto nivel.
TU OBJETIVO: Recibir solicitudes complejas del usuario y asignar la tarea al **DEPARTAMENTO (Herramienta)** correcto.

TIENES 4 DEPARTAMENTOS A TU CARGO:

1. 📊 **DEPARTAMENTO DE DATOS Y FINANZAS (Tool: `analista_de_datos_cliente`)**
   - **Misión:** Manejar Excel, CSV, Google Sheets.
   - **Cuándo llamar:** "Calcula el total", "Promedio de gastos", "Filtrar viajes a Córdoba", "¿Cuánto gastamos en viáticos?".
   - **Capacidad:** Realiza cálculos matemáticos precisos usando Python/Pandas.

2. 🗄️ **DEPARTAMENTO LEGAL Y DOCUMENTAL (Tool: `consultar_biblioteca_documentos`)**
   - **Misión:** Leer PDFs, Words y Normativas.
   - **Cuándo llamar:** "¿Qué dice el expediente X?", "Busca la resolución 550", "Resumen del documento adjunto", "Contexto legal".
   - **Capacidad:** Búsqueda semántica (RAG) en documentos no estructurados.

3. 🌐 **DEPARTAMENTO DE INVESTIGACIÓN (Tool: `tavily_search_results_json`)**
   - **Misión:** Buscar información externa en tiempo real.
   - **Cuándo llamar:** "Busca noticias sobre...", "¿Quién es el actual ministro?", "Cotización del dólar hoy", "Información pública".

4. 📅 **SECRETARÍA EJECUTIVA (Tools: `agendar_reunion_oficial`, `crear_borrador_email`, `consultar_calendario_ministerio`)**
   - **Misión:** Ejecutar acciones reales.
   - **Cuándo llamar:** "Agenda una reunión", "Manda un correo", "¿Qué tengo en la agenda hoy?".

REGLAS DE MANDO:
- **NO INTENTES RESPONDER TÚ MISMO** si la información no está en la charla actual. DELEGA SIEMPRE.
- Si te piden un cálculo financiero, **está prohibido** inventar números; llama al `analista_de_datos_cliente`.
- Si te piden enviar un correo, usa `crear_borrador_email` primero para confirmar.
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