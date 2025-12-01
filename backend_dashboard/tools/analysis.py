import pandas as pd
import logging
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
# --- CAMBIO CLAVE: Importamos la versión con CACHÉ ---
from tools.dashboard import obtener_datos_sheet_cached, SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID, procesar_fila_cliente

# Configurar logger
logger = logging.getLogger(__name__)

def get_dataframe_cliente():
    """
    Obtiene los datos usando el CACHÉ, los procesa y limpia la columna COSTO y FECHA.
    """
    # Usamos la función optimizada
    raw_data = obtener_datos_sheet_cached(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
    
    if not raw_data:
        logger.error("❌ No se obtuvieron datos (o caché vacío)")
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

    # --- NUEVA LÓGICA: Limpieza de FECHA (Datetime) ---
    # Esto es CRÍTICO para que el agente entienda "Noviembre 2025"
    if 'FECHA' in df.columns:
        # Intentamos convertir a datetime. 'coerce' convierte errores en NaT (Not a Time)
        # dayfirst=True ayuda con formatos latinos (DD/MM/YYYY)
        df['FECHA_DT'] = pd.to_datetime(df['FECHA'], errors='coerce', dayfirst=True)

    return df

def crear_agente_pandas():
    """Crea el agente especializado en DataFrames usando un modelo más potente."""
    df = get_dataframe_cliente()
    if df.empty:
        return None

    # --- CORRECCIÓN: Usamos el nombre específico del modelo para evitar errores 404 ---
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash-001", 
        temperature=0,
        max_retries=2
    )
    
    return create_pandas_dataframe_agent(
        llm,
        df,
        verbose=True,
        allow_dangerous_code=True, # Necesario para ejecutar Python
        handle_parsing_errors=True,
        # Prefix actualizado con instrucciones sobre FECHAS y COSTOS
        prefix="""Eres un experto analista de datos financiero utilizando Pandas. 
        Trabajas con un DataFrame 'df'.
        
        REGLAS DE DATOS:
        1. 'COSTO': Es float numérico. Suma directo: df['COSTO'].sum().
        2. 'FECHA_DT': Es columna datetime. Úsala para filtrar por tiempo.
           - Ejemplo Noviembre 2025: df[(df['FECHA_DT'].dt.month == 11) & (df['FECHA_DT'].dt.year == 2025)]
        3. 'FECHA': Es la fecha original en texto (úsala solo si FECHA_DT falla).
        4. Si te piden filtrar por texto, usa str.contains(..., case=False).
        
        Responde siempre con la respuesta final clara y concisa."""
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
        logger.error(f"Error en analista de datos: {e}", exc_info=True)
        return f"No pude realizar el cálculo debido a un error técnico: {str(e)}"