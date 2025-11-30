import pandas as pd
import logging # Importamos logging
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from tools.dashboard import obtener_datos_sheet, SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID, procesar_fila_cliente

# Configurar logger
logger = logging.getLogger(__name__)

def get_dataframe_cliente():
    raw_data = obtener_datos_sheet(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
    if not raw_data:
        logger.error("❌ No se obtuvieron datos crudos del Sheet")
        return pd.DataFrame()
    
    data_limpia = [procesar_fila_cliente(r) for r in raw_data]
    df = pd.DataFrame(data_limpia)
    
    # --- CORRECCIÓN: Limpieza numérica robusta y Logging ---
    if 'COSTO' in df.columns:
        # 1. LOG DE DEBUG: Ver qué datos llegan crudos (mira esto en tu terminal)
        logger.info(f"🔍 Muestra de datos COSTO crudos: {df['COSTO'].head(5).tolist()}")

        def limpiar_moneda(valor):
            if not valor: return 0
            val_str = str(valor).strip()
            # Eliminar símbolo de moneda y espacios
            val_str = val_str.replace('$', '').replace('USD', '').strip()
            
            # Caso Argentina/Europa: 1.000,00 -> Eliminar punto, reemplazar coma por punto
            # Pero cuidado si está en formato US: 1,000.00
            
            # Estrategia simple: dejar solo dígitos y el último separador decimal si existe
            if ',' in val_str and '.' in val_str:
                # Asumimos formato 1.000,00 (más común en Latam para sheets en español)
                val_str = val_str.replace('.', '').replace(',', '.')
            elif ',' in val_str:
                # Solo comas (100,50 o 1,000) -> Asumimos decimal
                val_str = val_str.replace(',', '.')
            
            # Eliminar cualquier otro caracter no numérico excepto el punto
            val_str = ''.join(c for c in val_str if c.isdigit() or c == '.')
            
            try:
                return float(val_str)
            except ValueError:
                return 0.0

        # Aplicar la limpieza fila por fila
        df['COSTO'] = df['COSTO'].apply(limpiar_moneda)
        
        # 2. LOG DE DEBUG: Ver datos después de limpiar
        logger.info(f"✅ Muestra de datos COSTO limpios: {df['COSTO'].head(5).tolist()}")
        logger.info(f"💰 Suma total verificada en Python: {df['COSTO'].sum()}")

    return df

# ... (El resto de la función crear_agente_pandas y analista_de_datos_cliente queda igual)
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