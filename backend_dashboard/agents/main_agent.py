import os
from datetime import datetime
import locale
from typing import List, Dict, Any, Union

# Intentamos configurar locale a español para la fecha; si falla, usamos el del sistema
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    pass

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate

# Imports de herramientas existentes
from tools.general import get_search_tool
from tools.email import crear_borrador_email
from tools.database import consultar_actas_reuniones, consultar_biblioteca_documentos
from tools.dashboard import (
    consultar_calendario_ministerio, 
    consultar_calendario_cliente
)

# --- NUEVO IMPORT: El Cerebro Matemático ---
from tools.analysis import analista_de_datos_cliente 

# 1. Configuración del Modelo
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0, # Temperatura 0 para máxima precisión
    max_retries=2,
)

# 2. Definir la fecha actual para contexto temporal
fecha_actual = datetime.now().strftime("%A %d de %B de %Y")

# --- FUNCIÓN CORREGIDA: Formateo de Historial ---
def format_chat_history(history: List[Any]) -> str:
    """
    Convierte el historial (que puede ser lista de dicts o de objetos Pydantic) 
    en texto plano para el contexto del LLM.
    """
    if not history or len(history) <= 1:
        return ""
    
    formatted = ["\n--- CONTEXTO PREVIO (MEMORIA) ---"]
    
    # Excluimos el último mensaje porque es el input actual que ya se pasa por separado
    history_to_process = history[:-1] 

    for msg in history_to_process:
        # LÓGICA HÍBRIDA: Detectar si es Diccionario o Objeto Pydantic
        if isinstance(msg, dict):
            sender = msg.get('sender')
            text = msg.get('text', '')
            ts = msg.get('timestamp')
        else:
            # Asumimos que es objeto Pydantic (Message) y usamos getattr por seguridad
            sender = getattr(msg, 'sender', None)
            text = getattr(msg, 'text', '')
            ts = getattr(msg, 'timestamp', None)

        role = "Usuario" if sender == 'user' else "Pitu (Asistente)"
        
        # Intentamos extraer hora del timestamp ISO para dar contexto temporal
        time_str = ""
        try:
            # Aseguramos que sea string antes de hacer slicing. CORRECCIÓN AQUÍ:
            ts_str = str(ts) if ts else ""
            if len(ts_str) > 16:
                time_str = f" ({ts_str[11:16]})" # Extrae HH:MM de ISO string
        except:
            pass
            
        formatted.append(f"{role}{time_str}: {text}")
    
    formatted.append("--- FIN MEMORIA ---\n")
    return "\n".join(formatted)

# --- DICCIONARIO DE DATOS Y LÓGICA DE NEGOCIO ---
contexto_datos = """
GLOSARIO DE TÉRMINOS Y REGLAS DE NEGOCIO DEL MINCYT:
- **EE (Expediente Electrónico):** Identificador administrativo único. Si una fila no tiene EE, es un borrador o gestión informal.
- **RENDICIÓN:** Estado crítico financiero. "Pendiente" es una alerta roja administrativa que requiere acción.
- **COSTO/PRECIO:** Siempre está en pesos argentinos (ARS) salvo que se especifique USD explícitamente.
- **AGENDA MINISTRO:** Tiene prioridad absoluta sobre cualquier evento de gestión interna.
- **SOSA:** Apellido frecuente en gestión, referente operativo clave.
"""

# 3. Prompt con Metodología "Chain of Thought"
system_instructions = f"""Eres Pitu, el Asistente Estratégico de Inteligencia del MinCYT.
HOY ES: {fecha_actual}.

{contexto_datos}

METODOLOGÍA DE PENSAMIENTO (COGNICIÓN):
Antes de responder o usar una herramienta, realiza este proceso mental interno:
1. **Analizar Intención:** ¿El usuario pide un dato puntual, un análisis comparativo (matemático) o información documental?
2. **Seleccionar Herramienta:**
   - ¿Cálculos, sumas, promedios o filtros por costo? -> `analista_de_datos_cliente` (EXCLUSIVO).
   - ¿Agenda simple o fechas? -> `consultar_calendario_...`
   - ¿Documentos, leyes o archivos PDF? -> `consultar_biblioteca_documentos`
3. **Ejecutar y Sintetizar:** No des datos sueltos. Si hay una cifra, dale contexto. Si falta el EE, adviértelo.

TU PROTOCOLO DE RESPUESTA:
- Cita siempre la fuente ("Según la agenda...", "El análisis indica...").
- Si te piden sumar o calcular, NUNCA lo hagas mentalmente. Usa `analista_de_datos_cliente`.
- Si te piden disponibilidad, cruza agenda 'ministerio' y 'cliente'.

HERRAMIENTAS DISPONIBLES:
- **analista_de_datos_cliente**: ¡TU CALCULADORA Y EXPERTO EN EXCEL! Úsala para sumas, conteos y filtros complejos.
- consultar_calendario_ministerio
- consultar_calendario_cliente
- consultar_biblioteca_documentos
- consultar_actas_reuniones
- tavily_search_results_json
- crear_borrador_email
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_instructions + "\n{history}"), # <--- AQUÍ INYECTAMOS LA MEMORIA
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# 4. Lista de Herramientas Actualizada
tools = [
    analista_de_datos_cliente,       
    get_search_tool(), 
    consultar_calendario_ministerio, 
    consultar_calendario_cliente,    
    crear_borrador_email, 
    consultar_actas_reuniones,
    consultar_biblioteca_documentos
]

# 5. Crear Agente
agent_runnable = create_tool_calling_agent(llm, tools, prompt)

agent = AgentExecutor(
    agent=agent_runnable,
    tools=tools,
    verbose=True,
    max_iterations=10, 
    handle_parsing_errors=True
)

# [MODIFICADO] Función actualizada para aceptar el historial
def get_agent_response(user_message: str, chat_history: List[Any] = []):
    try:
        print(f"🤖 Pitu Procesando ({fecha_actual}): {user_message}")
        
        # 1. Convertir el historial crudo en texto para el prompt
        history_text = format_chat_history(chat_history)
        
        # 2. Invocar al agente pasando tanto el input como el history
        response = agent.invoke({
            "input": user_message,
            "history": history_text 
        })
        return response["output"]
    except Exception as e:
        print(f"❌ Error Agente: {str(e)}")
        return f"Disculpa, hubo un error técnico al procesar tu solicitud: {str(e)}"