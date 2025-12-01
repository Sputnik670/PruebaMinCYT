import pandas as pd
import logging
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
# Importamos la lógica de datos con caché
from tools.dashboard import obtener_datos_sheet_cached, SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID, procesar_fila_cliente

# Configurar logger
logger = logging.getLogger(__name__)

def get_dataframe_cliente():
    """
    Obtiene los datos usando el CACHÉ, normaliza columnas y tipos de datos.
    """
    raw_data = obtener_datos_sheet_cached(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
    
    if not raw_data:
        logger.error("❌ No se obtuvieron datos para el DataFrame.")
        return pd.DataFrame()
    
    # Procesar lista de diccionarios
    data_limpia = [procesar_fila_cliente(r) for r in raw_data]
    df = pd.DataFrame(data_limpia)
    
    # 1. Limpieza de Moneda (COSTO)
    if 'COSTO' in df.columns:
        def limpiar_moneda(valor):
            if not valor: return 0.0
            val_str = str(valor).strip()
            # Quitar símbolos
            val_str = val_str.replace('$', '').replace('USD', '').replace('€', '').strip()
            
            # Detección de formato Europeo (1.000,50) vs US (1,000.50)
            if ',' in val_str and '.' in val_str:
                val_str = val_str.replace('.', '').replace(',', '.') # Asumimos formato AR/EU
            elif ',' in val_str:
                val_str = val_str.replace(',', '.') # Solo coma es decimal
            
            # Dejar solo números y punto
            val_str = ''.join(c for c in val_str if c.isdigit() or c == '.')
            
            try:
                return float(val_str)
            except ValueError:
                return 0.0

        df['COSTO'] = df['COSTO'].apply(limpiar_moneda)

    # 2. Limpieza de Fechas (CRÍTICO PARA FILTROS TEMPORALES)
    if 'FECHA' in df.columns:
        # 'coerce' pone NaT si falla. 'dayfirst=True' es vital para fechas latinas (DD/MM/YYYY)
        df['FECHA_DT'] = pd.to_datetime(df['FECHA'], errors='coerce', dayfirst=True)
        
        # Creamos columnas auxiliares para facilitar el filtrado natural
        df['MES'] = df['FECHA_DT'].dt.month
        df['ANIO'] = df['FECHA_DT'].dt.year
        df['DIA'] = df['FECHA_DT'].dt.day

    return df

def crear_agente_pandas():
    """Configura el agente de Pandas con Gemini Flash."""
    df = get_dataframe_cliente()
    if df.empty:
        return None

    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash-001", 
        temperature=0, # Cero creatividad para matemáticas, máxima precisión
        max_retries=2
    )
    
    # PROMPT DE INGENIERÍA DE DATOS
    prompt_prefix = """
    Eres un Analista de Datos Senior del MinCYT. Trabajas con un DataFrame de Pandas `df`.
    
    ESTRUCTURA DE DATOS:
    - 'COSTO': Float. Para sumar dinero usa: df['COSTO'].sum().
    - 'FECHA_DT': Datetime. Úsala para lógica temporal precisa.
    - 'MES' (int), 'ANIO' (int): Úsalas para agrupar (ej: "Gastos de Noviembre" -> df[df['MES']==11]).
    - 'MOTIVO / EVENTO': String. Contiene el nombre del evento.
    - 'LUGAR': String. Destino o ubicación.

    REGLAS DE OPERACIÓN:
    1. Si te piden "Total" o "Suma", calcula la suma de 'COSTO' aplicando los filtros necesarios.
    2. Si te piden filtrar por texto (ej: "Eventos en Cordoba"), usa: df[df['LUGAR'].str.contains('Cordoba', case=False, na=False)].
    3. Si el resultado es una tabla o lista larga, resume diciendo "Hay X registros, los primeros son...".
    4. NO inventes datos. Si el filtro devuelve vacío, dilo explícitamente.
    """

    return create_pandas_dataframe_agent(
        llm,
        df,
        verbose=True,
        allow_dangerous_code=True,
        handle_parsing_errors=True,
        return_intermediate_steps=True, # <--- CLAVE: Permite ver el razonamiento (código generado)
        prefix=prompt_prefix
    )

@tool
def analista_de_datos_cliente(consulta: str):
    """
    Agente de Análisis de Datos (Data Analyst).
    Úsalo para: Cálculos matemáticos, Sumar costos, Contar eventos, Filtrar por fechas complejas 
    (ej: "Gastos del mes pasado", "Promedio de costos en CABA").
    Retorna el resultado Y los pasos lógicos realizados.
    """
    try:
        agent = crear_agente_pandas()
        if not agent:
            return "Error: La base de datos interna está vacía o no disponible."
        
        logger.info(f"📊 Analista procesando: {consulta}")
        
        # Invocamos al agente
        response = agent.invoke({"input": consulta})
        
        output_final = response.get("output", "")
        pasos = response.get("intermediate_steps", [])

        # --- MEJORA DE CALIDAD DE RESPUESTA ---
        # Extraemos el "Pensamiento" (el código python que ejecutó) para darle contexto al Agente Principal
        contexto_ejecucion = ""
        if pasos:
            contexto_ejecucion = "\n\n--- EVIDENCIA DEL CÁLCULO (Código Ejecutado) ---\n"
            for action, observation in steps_summary(pasos):
                contexto_ejecucion += f"🔹 Acción: {action}\n🔸 Resultado Parcial: {observation}\n"
        
        return f"{output_final}{contexto_ejecucion}"

    except Exception as e:
        logger.error(f"Error en analista: {e}", exc_info=True)
        return f"Error técnico realizando el cálculo: {str(e)}"

def steps_summary(steps):
    """Helper para formatear los pasos intermedios de forma limpia"""
    summary = []
    for action, observation in steps:
        # Limpiamos el output de observación si es muy largo (ej: un dataframe entero)
        obs_str = str(observation)
        if len(obs_str) > 200:
            obs_str = obs_str[:200] + "... (truncado)"
        
        # action es un objeto AgentAction, action.tool_input suele ser el código python
        code = getattr(action, 'tool_input', str(action))
        summary.append((code, obs_str))
    return summary