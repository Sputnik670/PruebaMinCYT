import pandas as pd
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from tools.dashboard import obtener_datos_sheet, SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID, procesar_fila_cliente

# Reutilizamos tu lógica de extracción de Google Sheets
def get_dataframe_cliente():
    raw_data = obtener_datos_sheet(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
    if not raw_data:
        return pd.DataFrame()
    
    # Procesamos y limpiamos (importante para que los números sean números)
    data_limpia = [procesar_fila_cliente(r) for r in raw_data]
    df = pd.DataFrame(data_limpia)
    
    # CONVERSIÓN DE TIPOS (CRÍTICO PARA QUE PUEDA SUMAR)
    # Limpiamos el signo $ y las comas para convertir a float
    if 'COSTO' in df.columns:
        df['COSTO'] = df['COSTO'].astype(str).str.replace(r'[$,.]', '', regex=True).replace('', '0')
        df['COSTO'] = pd.to_numeric(df['COSTO'], errors='coerce').fillna(0)
    
    return df

# Creamos el Agente de Pandas
def crear_agente_pandas():
    df = get_dataframe_cliente()
    if df.empty:
        return None

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    return create_pandas_dataframe_agent(
        llm,
        df,
        verbose=True,
        allow_dangerous_code=True, # Necesario para que ejecute Python
        handle_parsing_errors=True
    )

# ESTA ES LA HERRAMIENTA QUE USARÁ PITU
@tool
def analista_de_datos_cliente(consulta: str):
    """
    PODEROSA herramienta para análisis numérico, sumas, promedios, filtrado complejo 
    y conteo de la Agenda/Gestión Interna. 
    Úsala cuando pregunten 'cuánto suma', 'cuántos eventos', 'promedio de gastos', 
    o búsquedas con múltiples variables (ej: 'eventos en tal lugar con costo mayor a X').
    NO la uses para cosas simples como 'qué hay mañana'.
    """
    try:
        agent = crear_agente_pandas()
        if not agent:
            return "Error: No se pudieron cargar los datos para el análisis."
        
        # Le pedimos al agente de pandas que resuelva la consulta
        respuesta = agent.invoke({"input": consulta})
        return respuesta["output"]
    except Exception as e:
        return f"Error en el análisis de datos: {str(e)}"