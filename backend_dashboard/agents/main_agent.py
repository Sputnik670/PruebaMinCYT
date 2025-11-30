import os
from datetime import datetime
import locale

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

# 3. Prompt de "Ejecutivo de Alto Nivel" con el Analista de Datos Integrado
system_instructions = f"""Eres Pitu, el Asistente Estratégico de Inteligencia del MinCYT.
HOY ES: {fecha_actual}. Usa esta fecha como ancla para cualquier consulta de "hoy", "mañana" o "la próxima semana".

TU PROTOCOLO DE RESPUESTA (SÍGUELO ESTRICTAMENTE):

1. 📊 **Análisis Numérico y Financiero (PRIORITARIO):**
   - Si te piden **SUMAR costos, calcular TOTALES, PROMEDIOS, contar eventos** o hacer filtros complejos (ej: "eventos en CABA con costo mayor a X"), USA INMEDIATAMENTE la herramienta `analista_de_datos_cliente`.
   - NO intentes sumar "leyendo" la lista de eventos. Usa el analista, él es tu calculadora y experto en Excel.

2. 📅 **Validación Cruzada de Agenda:** - Si te piden disponibilidad horaria, cruza SIEMPRE 'ministerio' y 'cliente'.

3. 📂 **Ubicación de Datos:**
   - **Matemáticas/Filtros/Costos:** -> `analista_de_datos_cliente`
   - **Lectura simple de agenda:** -> `consultar_calendario_...`
   - **Documentos/Reglamentos:** -> `consultar_biblioteca_documentos`
   - **Hechos Pasados:** -> `consultar_actas_reuniones`

4. **Citas y Asertividad:** Cita la fuente ("Según el análisis de datos...", "En la agenda figura..."). Si no hay datos, dilo claramente.

HERRAMIENTAS DISPONIBLES:
- **analista_de_datos_cliente**: ¡ÚSALA PARA CUALQUIER CÁLCULO, SUMA O FILTRO DE LA GESTIÓN INTERNA!
- consultar_calendario_ministerio
- consultar_calendario_cliente
- consultar_biblioteca_documentos
- consultar_actas_reuniones
- tavily_search_results_json
- crear_borrador_email
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_instructions),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# 4. Lista de Herramientas Actualizada (Incluye el Analista)
tools = [
    analista_de_datos_cliente,       # <--- LA NUEVA ESTRELLA MATEMÁTICA
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
    max_iterations=10, # Damos un poco más de margen por si el analista de pandas necesita reintentar código
    handle_parsing_errors=True
)

def get_agent_response(user_message: str):
    try:
        print(f"🤖 Pitu Procesando ({fecha_actual}): {user_message}")
        response = agent.invoke({"input": user_message})
        return response["output"]
    except Exception as e:
        print(f"❌ Error Agente: {str(e)}")
        return "Disculpa, hubo un error técnico al procesar tu solicitud."