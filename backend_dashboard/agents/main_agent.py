import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo  
import locale
import operator
from typing import List, Any, TypedDict, Annotated

try: locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except: pass

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

# --- CORRECCIÓN DE IMPORTACIÓN DE MEMORIA (Blindaje) ---
try:
    # Intento 1: Ubicación estándar
    from langchain.memory import ConversationSummaryBufferMemory
except ImportError:
    try:
        # Intento 2: Ubicación moderna (LangChain 0.3+)
        from langchain_community.memory import ConversationSummaryBufferMemory
    except ImportError:
        # Intento 3: Ubicación legacy
        from langchain.chains.conversation.memory import ConversationSummaryBufferMemory
# -------------------------------------------------------

from langchain_community.chat_message_histories import ChatMessageHistory

# --- IMPORTACIÓN DE HERRAMIENTAS ---
from tools.general import get_search_tool
from tools.email import crear_borrador_email
from tools.database import consultar_actas_reuniones, consultar_biblioteca_documentos
from tools.analysis import analista_de_datos_cliente
from tools.actions import agendar_reunion_oficial, enviar_email_real

logger = logging.getLogger(__name__)

# Usamos Flash con temperatura 0 para máxima precisión
llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash-001", temperature=0, max_retries=2)

def get_memory_aware_history(history_list):
    chat_history = ChatMessageHistory()
    
    for msg in (history_list or []):
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
    
    mem = ConversationSummaryBufferMemory(
        llm=llm, 
        chat_memory=chat_history, 
        max_token_limit=4000, 
        return_messages=True, 
        memory_key="chat_history"
    )
    return mem.load_memory_variables({})["chat_history"]

def obtener_fecha_hora_local():
    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    return datetime.now(tz).strftime("%A %d/%m/%Y, %H:%M hs")

# --- PROMPT DEL DIRECTOR (VERSIÓN AUTORITARIA) ---
sys_prompt = f"""Eres el **Director de Operaciones (COO)** del MinCYT.
📅 **FECHA ACTUAL:** {obtener_fecha_hora_local()}

### ⚡ DIRECTIVA SUPREMA: ACCIÓN INMEDIATA
- **PROHIBIDO** pedir permiso para usar herramientas.
- **PROHIBIDO** decir "Voy a buscar..." o "¿Puedo consultar...?".
- SI necesitas un dato, **LLAMA A LA HERRAMIENTA DIRECTAMENTE**.
- SI el usuario pregunta algo que requiere datos, tu única salida válida es invocar una Tool.

### 🧠 CÓMO PENSAR (MEMORIA):
1. Lee la pregunta del usuario.
2. Mira el historial de chat para entender el contexto (ej: "¿Cuándo fue?" se refiere al evento mencionado antes).
3. **REFORMULA** la consulta para la herramienta incluyendo TODOS los detalles (Nombres, Montos, Fechas).
4. **EJECUTA**.

### TUS DEPARTAMENTOS (HERRAMIENTAS):

1. 📊 **DATOS Y AGENDA (Tool: `analista_de_datos_cliente`)**
   - Úsala para: Viajes, Gastos, Misiones, Agenda Oficial, Funcionarios.
   - *Query Ejemplo:* "Fecha y detalles del viaje a Londres de 7500 USD mencionado antes".

2. 🗄️ **LEGAL (Tool: `consultar_biblioteca_documentos`)**
   - Úsala para: Leer PDFs o documentos subidos.

3. 🌐 **WEB (Tool: `tavily_search_results_json`)**
   - Úsala para: Info de internet.

4. 📅 **ACCIÓN (Tools: `agendar_reunion_oficial`, `crear_borrador_email`)**
   - Úsala para: Agendar o enviar mails.

¡NO CHARLES! ¡EJECUTA!
"""

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

class State(TypedDict): messages: Annotated[List[BaseMessage], operator.add]

def call_model(s): 
    msgs = s['messages']
    sys_msg = SystemMessage(content=sys_prompt)
    if isinstance(msgs[0], SystemMessage):
        msgs[0] = sys_msg
    else:
        msgs.insert(0, sys_msg)
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
        memory_messages = get_memory_aware_history(hist)
        
        # Invocamos al grafo
        res = app.invoke(
            {"messages": memory_messages + [HumanMessage(content=msg)]}, 
            config={"recursion_limit": 20}
        )
        
        # --- 🕵️ ZONA DE DIAGNÓSTICO ---
        print("\n" + "="*40)
        print(f"🧐 DIAGNÓSTICO PARA: '{msg}'")
        
        # Revisamos los últimos mensajes para ver si hubo uso de herramientas
        messages = res["messages"]
        tool_used = False
        
        for m in messages:
            # Si el modelo pidió usar una herramienta
            if m.type == "ai" and m.tool_calls:
                print(f"🤖 INTENTO DE TOOL: {m.tool_calls[0]['name']}")
                print(f"   Parámetros: {m.tool_calls[0]['args']}")
                tool_used = True
            
            # Si la herramienta respondió (Esto es lo IMPORTANTE)
            if m.type == "tool":
                content_preview = str(m.content)[:500] # Solo los primeros 500 chars
                print(f"🔧 RESPUESTA DE TOOL: {content_preview}...")
                if "Error" in str(m.content) or "[]" == str(m.content):
                    print("⚠️  ¡LA HERRAMIENTA DEVOLVIÓ VACÍO O ERROR!")
        
        if not tool_used:
            print("⚠️  EL AGENTE NO LLAMÓ A NINGUNA HERRAMIENTA (Posible Alucinación Pura)")
            
        print("="*40 + "\n")
        # -------------------------------

        return res["messages"][-1].content
    except Exception as e:
        logger.error(f"Error en agente: {e}")
        return "Tuve un error técnico momentáneo procesando tu solicitud."