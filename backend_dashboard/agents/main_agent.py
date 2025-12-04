import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo  
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

# --- IMPORTACIÓN DE HERRAMIENTAS ---
from tools.general import get_search_tool
from tools.email import crear_borrador_email
from tools.database import consultar_actas_reuniones, consultar_biblioteca_documentos
# (CAMBIO) Eliminamos las herramientas crudas de aquí. 
# El agente solo debe ver al "Analista" para evitar confusiones.
from tools.analysis import analista_de_datos_cliente
from tools.actions import agendar_reunion_oficial, enviar_email_real

logger = logging.getLogger(__name__)

# Modelo: Usamos Flash con temperatura 0 para precisión en instrucciones
llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash-001", temperature=0, max_retries=2)

def get_memory_aware_history(history_list):
    """
    Recupera el historial de chat de forma segura.
    Mantenemos ConversationSummaryBufferMemory porque priorizas la ROBUSTEZ.
    Esto asegura que el bot tenga "memoria fotográfica" de lo reciente y "contexto general" de lo antiguo.
    """
    chat_history = ChatMessageHistory()
    
    # Procesamos todo menos el último mensaje
    for msg in (history_list[:-1] if history_list else []):
        if isinstance(msg, dict):
            txt = msg.get('text', '')
            sender = msg.get('sender', '')
        else:
            txt = getattr(msg, 'text', '')
            sender = getattr(msg, 'sender', '')

        if sender == 'user': 
            chat_history.add_user_message(txt)
        else: 
            chat_history.add_ai_message(txt)
    
    # Aumentamos el límite de tokens para garantizar más contexto preciso antes de resumir
    mem = ConversationSummaryBufferMemory(
        llm=llm, 
        chat_memory=chat_history, 
        max_token_limit=3000, 
        return_messages=True, 
        memory_key="chat_history"
    )
    return mem.load_memory_variables({})["chat_history"]

# --- 2. CÁLCULO DE FECHA LOCAL ---
def obtener_fecha_hora_local():
    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    ahora = datetime.now(tz)
    # Formato amigable para el LLM: "Jueves 25 de Mayo, 14:30 hs"
    return ahora.strftime("%A %d/%m/%Y, %H:%M hs")

# --- PROMPT DEL MANAGER (ROUTER / ORQUESTADOR) ---
# Inyectamos la función de hora en el prompt dinámicamente
sys_prompt = f"""Eres el **Director de Operaciones (COO)** del MinCYT.
📅 **FECHA Y HORA ACTUAL (Argentina):** {obtener_fecha_hora_local()}

TU ROL: Orquestador estratégico.
TU OBJETIVO: Delegar inmediatamente al departamento correcto. 
CRÍTICO: **NO HAGAS PREGUNTAS DE ACLARACIÓN** sobre "¿qué base de datos usar?". Asume siempre que la herramienta de datos tiene acceso a TODO (Público y Privado).

TIENES 4 DEPARTAMENTOS A TU CARGO:

1. 📊 **DEPARTAMENTO DE DATOS UNIFICADOS (Tool: `analista_de_datos_cliente`)**
   - **Misión:** Es tu Autoridad Central de Datos. Contiene la FUSIÓN de la Agenda Pública (Ministerio) y la Gestión Interna (Cliente).
   - **Cuándo llamar:** - Siempre que pregunten por "Eventos", "Agenda", "Calendario" o "Reuniones".
     - Consultas con filtros: "Nacional", "Internacional", "CABA", "Ministro".
     - Consultas financieras: "Gastos", "Presupuesto", "Costos".
   - **Instrucción:** Si el usuario pregunta "¿Hay eventos nacionales?", LLAMA A ESTA HERRAMIENTA. No preguntes "¿en qué calendario?".

2. 🗄️ **DEPARTAMENTO LEGAL Y DOCUMENTAL (Tool: `consultar_biblioteca_documentos`)**
   - **Misión:** Búsqueda Semántica en documentos (PDF, Word, TXT).
   - **Cuándo llamar:** Solo si preguntan por el *contenido* de un archivo subido, normativas o textos legales.

3. 🌐 **DEPARTAMENTO DE INVESTIGACIÓN (Tool: `tavily_search_results_json`)**
   - **Misión:** Buscar información externa en internet.
   - **Cuándo llamar:** Noticias recientes, datos que no dependen del ministerio.

4. 📅 **SECRETARÍA EJECUTIVA (Tools: `agendar_reunion_oficial`, `crear_borrador_email`)**
   - **Misión:** Ejecutar acciones reales.
   - **Cuándo llamar:** "Agendar reunión", "Enviar correo". Usa siempre la fecha actual como referencia.

REGLAS DE MANDO:
- Ante la duda sobre datos, usa la **Herramienta 1**. Ella sabrá filtrar si es dato público o privado.
- Solo responde al usuario cuando la herramienta te haya dado la información.
"""

# (CAMBIO CRÍTICO) Lista de herramientas LIMPIA
# Quitamos consultar_calendario_ministerio y consultar_calendario_cliente
# para forzar el uso del analista_de_datos_cliente (que tiene la data unificada).
tools = [
    analista_de_datos_cliente, 
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
    # Actualizamos el prompt de sistema en cada llamada para que la hora esté fresca
    msgs = s['messages']
    # Si el primer mensaje es System, lo actualizamos. Si no, lo insertamos.
    if isinstance(msgs[0], SystemMessage):
        msgs[0] = SystemMessage(content=sys_prompt)
    else:
        msgs.insert(0, SystemMessage(content=sys_prompt))
        
    return {"messages": [llm_with_tools.invoke(msgs)]}

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
        # Recuperamos historial con memoria inteligente
        memory_messages = get_memory_aware_history(hist)
        
        # Invocamos el grafo
        res = app.invoke(
            {"messages": memory_messages + [HumanMessage(content=msg)]}, 
            config={"recursion_limit": 20}
        )
        return res["messages"][-1].content
    except Exception as e:
        logger.error(f"Error en agente: {e}")
        return "Tuve un error técnico momentáneo procesando tu solicitud."