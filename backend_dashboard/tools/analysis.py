import pandas as pd
import logging
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
# Asegúrate de que esta importación coincida con tu estructura de carpetas
from tools.dashboard import obtener_datos_sheet, SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID, procesar_fila_cliente

# Configurar logger
logger = logging.getLogger(__name__)

def get_dataframe_cliente():
    """
    Obtiene los datos crudos, los procesa y limpia la columna COSTO para análisis numérico.
    """
    raw_data = obtener_datos_sheet(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
    if not raw_data:
        logger.error("❌ No se obtuvieron datos crudos del Sheet")
        return pd.DataFrame()
    
    data_limpia = [procesar_fila_cliente(r) for r in raw_data]
    df = pd.DataFrame(data_limpia)
    
    # --- Limpieza numérica robusta ---
    if 'COSTO' in df.columns:
        logger.info(f"🔍 Muestra de datos COSTO crudos: {df['COSTO'].head(5).tolist()}")

        def limpiar_moneda(valor):
            if not valor: return 0.0
            val_str = str(valor).strip()
            # Eliminar símbolos de moneda y texto
            val_str = val_str.replace('$', '').replace('USD', '').replace('€', '').strip()
            
            # Lógica para detectar formato europeo (1.000,00) vs americano (1,000.00)
            if ',' in val_str and '.' in val_str:
                # Asumimos formato latam/europeo: punto para miles, coma para decimales
                val_str = val_str.replace('.', '').replace(',', '.')
            elif ',' in val_str:
                # Solo comas -> decimal
                val_str = val_str.replace(',', '.')
            
            # Dejar solo dígitos y punto
            val_str = ''.join(c for c in val_str if c.isdigit() or c == '.')
            
            try:
                return float(val_str)
            except ValueError:
                return 0.0

        # Aplicar la limpieza
        df['COSTO'] = df['COSTO'].apply(limpiar_moneda)
        
        logger.info(f"✅ Muestra de datos COSTO limpios: {df['COSTO'].head(5).tolist()}")
        logger.info(f"💰 Suma total verificada en Python: {df['COSTO'].sum()}")

    return df

def crear_agente_pandas():
    """Crea el agente especializado en DataFrames usando un modelo más potente."""
    df = get_dataframe_cliente()
    if df.empty:
        return None

    # --- CAMBIO CLAVE: Usamos un modelo más potente para razonamiento lógico/matemático ---
    # Gemini 1.5 Pro es superior generando código Pandas sin errores.
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-pro", 
        temperature=0,
        max_retries=2
    )
    
    return create_pandas_dataframe_agent(
        llm,
        df,
        verbose=True,
        allow_dangerous_code=True, # Necesario para ejecutar Python
        handle_parsing_errors=True,
        # Prefix le da "personalidad" y reglas al experto en datos
        prefix="""Eres un experto analista de datos financiero utilizando Pandas. 
        Trabajas con un DataFrame que contiene información de gestión y costos.
        IMPORTANTE:
        1. La columna 'COSTO' ya es numérica (float). No intentes convertirla de nuevo.
        2. Si te piden sumar, usa df['COSTO'].sum().
        3. Si te piden filtrar por texto, usa str.contains(..., case=False).
        Responde siempre con la respuesta final clara."""
    )

# ESTA ES LA HERRAMIENTA QUE USARÁ EL AGENTE PRINCIPAL
@tool
def analista_de_datos_cliente(consulta: str):
    """
    PODEROSA herramienta para análisis numérico, sumas, promedios, filtrado complejo 
    y conteo de la Agenda/Gestión Interna. 
    Úsala cuando pregunten 'cuánto suma', 'cuántos eventos', 'promedio de gastos', 
    o búsquedas con múltiples variables (ej: 'eventos en tal lugar con costo mayor a X').
    NO la uses para cosas simples como 'qué hay mañana' (usa el calendario para eso).
    """
    try:
        agent = crear_agente_pandas()
        if not agent:
            return "Error: No se pudieron cargar los datos para el análisis."
        
        # Le pedimos al agente de pandas que resuelva la consulta
        respuesta = agent.invoke({"input": consulta})
        return respuesta["output"]
    except Exception as e:
        logger.error(f"Error en analista de datos: {e}")
        return f"No pude realizar el cálculo debido a un error técnico: {str(e)}"