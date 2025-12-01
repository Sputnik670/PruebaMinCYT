import pandas as pd
import logging
import re
from datetime import datetime
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from tools.dashboard import obtener_datos_sheet_cached, SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID, procesar_fila_cliente

logger = logging.getLogger(__name__)

# ... (Mantén tus funciones parse_money_value y extraer_fecha_inteligente igual que antes) ...
# Solo me aseguro de incluir parse_money_value aquí para referencia, pero usa la que ya tienes si funciona bien.

def parse_money_value(valor):
    """Extrae (Moneda, Monto) limpiando símbolos."""
    if not valor: return "ARS", 0.0
    val_str = str(valor).strip().upper()
    
    moneda = "ARS"
    if any(s in val_str for s in ["USD", "U$S", "DOLAR", "US$"]): moneda = "USD"
    elif any(s in val_str for s in ["EUR", "EURO", "€"]): moneda = "EUR"
    
    # Limpieza agresiva para dejar solo numeros y punto/coma
    val_limpio = re.sub(r'[^\d.,-]', '', val_str)
    if not val_limpio: return moneda, 0.0

    # Lógica para detectar decimales vs miles
    if ',' in val_limpio and '.' in val_limpio:
        if val_limpio.rfind(',') > val_limpio.rfind('.'): # Caso 1.000,50
            val_limpio = val_limpio.replace('.', '').replace(',', '.')
        else: # Caso 1,000.50
            val_limpio = val_limpio.replace(',', '')
    elif ',' in val_limpio: # Caso 500,50
        val_limpio = val_limpio.replace(',', '.')
    
    try:
        monto = float(val_limpio)
    except:
        monto = 0.0
    return moneda, monto

# ... extraer_fecha_inteligente se queda igual ...

def get_dataframe_cliente():
    raw_data = obtener_datos_sheet_cached(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
    if not raw_data: return pd.DataFrame()
    
    data_limpia = [procesar_fila_cliente(r) for r in raw_data]
    df = pd.DataFrame(data_limpia)
    
    # --- PRE-PROCESAMIENTO ROBUSTO ---
    if 'COSTO' in df.columns:
        parsed = df['COSTO'].apply(parse_money_value)
        df['MONEDA'] = parsed.apply(lambda x: x[0])
        df['MONTO'] = parsed.apply(lambda x: x[1])
        # Aseguramos que MONTO sea float para que el agente pueda sumar sin errores
        df['MONTO'] = df['MONTO'].astype(float)

    if 'FECHA' in df.columns:
        df['FECHA_DT'] = df['FECHA'].apply(extraer_fecha_inteligente)
        df['MES'] = df['FECHA_DT'].apply(lambda x: x.month if pd.notnull(x) else 0)
        df['ANIO'] = df['FECHA_DT'].apply(lambda x: x.year if pd.notnull(x) else 0)

    return df

def crear_agente_pandas():
    df = get_dataframe_cliente()
    if df.empty: return None

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # --- PROMPT DE INGENIERÍA INVERSA PARA GARANTIZAR EL FORMATO ---
    prompt_prefix = """
    Estás trabajando con un DataFrame de Pandas 'df'.
    Estructura de columnas clave:
    - 'MONEDA': La divisa (ARS, USD, EUR).
    - 'MONTO': El valor numérico (float).
    - 'MOTIVO / EVENTO': Descripción.
    - 'MES' y 'ANIO': Enteros para filtrar fechas.

    TU MISIÓN: Calcular costos totales agrupados por moneda.

    PASOS OBLIGATORIOS (Ejecuta código Python):
    1. Filtra el 'df' según lo que pida el usuario (mes, evento, etc).
    2. Agrupa por 'MONEDA' y suma la columna 'MONTO'.
    3. Imprime el resultado del agrupamiento.

    FORMATO DE SALIDA ESTRICTO:
    Debes responder EXACTAMENTE con este formato (reemplaza X e Y por los números):
    "el costo es = EURO: X Y DOLAR: Y Y PESOS: Z"
    
    Si una moneda es 0, no la incluyas.
    NO escribas código en la respuesta final, solo la frase formateada.
    """

    return create_pandas_dataframe_agent(
        llm, 
        df, 
        verbose=True, 
        allow_dangerous_code=True,
        prefix=prompt_prefix,
        handle_parsing_errors=True
    )

@tool
def analista_de_datos_cliente(consulta: str):
    """
    Calculadora financiera OFICIAL.
    Úsala SIEMPRE que el usuario pregunte por 'costos', 'presupuesto', 'cuánto se gastó', 'suma de gastos'.
    """
    try:
        agent = crear_agente_pandas()
        if not agent: return "Error: No hay datos disponibles en la planilla."
        
        # Invocamos al agente
        response = agent.invoke({"input": consulta})
        return response["output"]

    except Exception as e:
        logger.error(f"Error analista: {e}")
        return f"No pude realizar el cálculo debido a un error técnico: {e}"