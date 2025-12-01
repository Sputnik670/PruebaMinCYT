import pandas as pd
import logging
import re
from datetime import datetime
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from tools.dashboard import obtener_datos_sheet_cached, SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID, procesar_fila_cliente

logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DE CAMBIO ---
COTIZACION = {
    "USD": 1200.0,
    "EUR": 1300.0,
    "ARS": 1.0
}

def parse_money_value(valor):
    """Extrae (Moneda, Monto)."""
    if not valor: return "ARS", 0.0
    val_str = str(valor).strip().upper()
    
    moneda = "ARS"
    if any(s in val_str for s in ["USD", "U$S", "DOLAR", "DÓLAR", "US$"]):
        moneda = "USD"
    elif any(s in val_str for s in ["EUR", "EURO", "€"]):
        moneda = "EUR"
    
    val_limpio = re.sub(r'[^\d.,-]', '', val_str)
    if not val_limpio: return moneda, 0.0

    last_comma = val_limpio.rfind(',')
    last_point = val_limpio.rfind('.')

    if last_comma > -1 and last_point > -1:
        if last_comma > last_point: 
            val_limpio = val_limpio.replace('.', '').replace(',', '.')
        else:
            val_limpio = val_limpio.replace(',', '')
    elif last_comma > -1:
        val_limpio = val_limpio.replace('.', '').replace(',', '.')
    
    try:
        monto = float(val_limpio)
    except ValueError:
        monto = 0.0
        
    return moneda, monto

def extraer_fecha_inteligente(valor):
    if not valor: return pd.NaT
    val_str = str(valor).strip()
    try:
        return pd.to_datetime(val_str, dayfirst=True)
    except:
        pass
    match = re.search(r'(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)', val_str)
    if match:
        try:
            txt = match.group(1)
            if len(txt) <= 5: txt += f"/{datetime.now().year}"
            return pd.to_datetime(txt, dayfirst=True)
        except:
            pass
    return pd.NaT

def get_dataframe_cliente():
    raw_data = obtener_datos_sheet_cached(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
    if not raw_data:
        return pd.DataFrame()
    
    data_limpia = [procesar_fila_cliente(r) for r in raw_data]
    df = pd.DataFrame(data_limpia)
    
    # Procesamiento de Moneda
    if 'COSTO' in df.columns:
        parsed = df['COSTO'].apply(parse_money_value)
        df['MONEDA'] = parsed.apply(lambda x: x[0])
        df['MONTO'] = parsed.apply(lambda x: x[1])
        
        # IMPORTANTE: No creamos columna de referencia en ARS para no confundir al agente.

    # Procesamiento de Fechas
    if 'FECHA' in df.columns:
        df['FECHA_DT'] = df['FECHA'].apply(extraer_fecha_inteligente)
        df['MES'] = df['FECHA_DT'].dt.month
        df['ANIO'] = df['FECHA_DT'].dt.year

    return df

def crear_agente_pandas():
    df = get_dataframe_cliente()
    if df.empty: return None

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # PROMPT DE INGENIERÍA DE DATOS
    prompt_prefix = """
    Eres un Analista de Costos Riguroso. Trabajas con un DataFrame `df`.
    
    TU OBJETIVO: Calcular el costo total EXACTO agrupado por divisa.
    
    INSTRUCCIONES OBLIGATORIAS:
    1. Filtra los datos según la consulta (mes, año, tema, etc.).
    2. Agrupa los resultados por la columna 'MONEDA'.
    3. Suma la columna 'MONTO' para cada moneda.
    4. NO conviertas monedas. Reporta la suma de cada una por separado.
    
    EJEMPLO DE RESPUESTA CORRECTA:
    "Para diciembre 2025 encontré 5 eventos. Los costos son:
    - USD: 12,500.00
    - EUR: 3,200.00
    - ARS: 1,500,000.00"
    
    EJEMPLO INCORRECTO (NO HACER):
    "El costo total es $30,000,000 pesos." (Prohibido sumar monedas distintas).
    """

    return create_pandas_dataframe_agent(
        llm, 
        df, 
        verbose=True, 
        allow_dangerous_code=True,
        return_intermediate_steps=True,
        prefix=prompt_prefix,
        handle_parsing_errors=True
    )

@tool
def analista_de_datos_cliente(consulta: str):
    """Calculadora financiera para sumar costos y filtrar agenda."""
    try:
        agent = crear_agente_pandas()
        if not agent: return "Error: Sin datos."
        
        response = agent.invoke({"input": consulta})
        
        output = response.get("output", "")
        # Agregamos el código de debug para que el agente principal confíe
        pasos = response.get("intermediate_steps", [])
        debug_code = ""
        if pasos:
             for action, obs in pasos:
                 if hasattr(action, 'tool_input'):
                     debug_code += f"\n[Código generado]: {action.tool_input}\n"

        return f"{output}\n{debug_code}" 

    except Exception as e:
        logger.error(f"Error analista: {e}")
        return f"Error de cálculo: {e}"