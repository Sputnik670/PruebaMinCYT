# backend_dashboard/tools/analysis.py

import pandas as pd
import logging
import re
import traceback
from datetime import datetime, timedelta
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from tools.dashboard import obtener_datos_sheet_cached, SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID, procesar_fila_cliente

logger = logging.getLogger(__name__)

# --- 1. FUNCIONES DE LIMPIEZA Y PREPARACIÓN (ETL) ---

def parse_money_value(valor):
    """(Mismo código que ya tienes para parse_money_value...)"""
    if not valor: return "ARS", 0.0
    val_str = str(valor).strip().upper()
    moneda = "ARS"
    if any(s in val_str for s in ["USD", "U$S", "DOLAR", "DÓLAR", "US$", "DOLARES"]):
        moneda = "USD"
    elif any(s in val_str for s in ["EUR", "EURO", "€", "EUROS"]):
        moneda = "EUR"
    val_limpio = re.sub(r'[^\d.,-]', '', val_str)
    if not val_limpio: return moneda, 0.0
    if ',' in val_limpio and '.' in val_limpio:
        last_comma = val_limpio.rfind(',')
        last_point = val_limpio.rfind('.')
        if last_comma > last_point: val_limpio = val_limpio.replace('.', '').replace(',', '.')
        else: val_limpio = val_limpio.replace(',', '')
    elif ',' in val_limpio:
        val_limpio = val_limpio.replace(',', '.')
    try:
        monto = float(val_limpio)
    except ValueError:
        monto = 0.0
    return moneda, monto

# --- NUEVA LÓGICA DE FECHAS MEJORADA ---
def obtener_meses_involucrados(fecha_str):
    """
    Analiza strings como '30-11 al 06-12' y devuelve una lista de nombres de meses.
    Ej: 'Noviembre, Diciembre'
    """
    if not fecha_str: return "Sin Fecha"
    texto = str(fecha_str).lower()
    
    # Mapeo de meses
    meses_map = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
        7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    
    # Buscar TODAS las fechas posibles en el string
    # Regex busca patrones dd/mm o dd-mm
    matches = re.findall(r'(\d{1,2})[/-](\d{1,2})', texto)
    
    meses_detectados = set()
    anio_actual = datetime.now().year
    
    # Si encontramos patrones de fecha
    for dia, mes in matches:
        try:
            m = int(mes)
            if 1 <= m <= 12:
                meses_detectados.add(meses_map[m])
        except: pass

    # Si pandas ya lo había parseado como fecha única en otra columna, lo agregamos
    try:
        dt = pd.to_datetime(fecha_str, dayfirst=True)
        if not pd.isna(dt):
            meses_detectados.add(meses_map[dt.month])
    except: pass

    if not meses_detectados:
        return "Fecha Desconocida"
        
    return ", ".join(sorted(list(meses_detectados)))

def extraer_fecha_inteligente(valor):
    """Intenta parsear la FECHA DE INICIO principal."""
    if not valor: return pd.NaT
    val_str = str(valor).strip()
    
    # Prioridad: Buscar la primera fecha que aparezca en el string
    match = re.search(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', val_str)
    if match:
        try:
            dia, mes = match.group(1), match.group(2)
            anio = match.group(3)
            if not anio: anio = datetime.now().year
            return pd.to_datetime(f"{dia}/{mes}/{anio}", dayfirst=True)
        except:
            pass
            
    try:
        return pd.to_datetime(val_str, dayfirst=True)
    except:
        return pd.NaT

def get_dataframe_cliente():
    """Construye el DataFrame maestro con datos limpios."""
    try:
        raw_data = obtener_datos_sheet_cached(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
        if not raw_data:
            return pd.DataFrame()
        
        data_limpia = [procesar_fila_cliente(r) for r in raw_data]
        df = pd.DataFrame(data_limpia)
        
        if 'COSTO' in df.columns:
            parsed = df['COSTO'].apply(parse_money_value)
            df['MONEDA'] = parsed.apply(lambda x: x[0])
            df['MONTO'] = parsed.apply(lambda x: x[1]).astype(float)

        if 'FECHA' in df.columns:
            # 1. Fecha exacta para ordenamiento
            df['FECHA_DT'] = df['FECHA'].apply(extraer_fecha_inteligente)
            
            # 2. COLUMNA CLAVE: MESES_IMPACTO
            # Esto permitirá que "30/11 al 06/12" aparezca como "Noviembre, Diciembre"
            df['MESES_IMPACTO'] = df['FECHA'].apply(obtener_meses_involucrados)

        return df
    except Exception as e:
        logger.error(f"Error construyendo DataFrame: {e}")
        return pd.DataFrame()

# --- 2. CONFIGURACIÓN DEL AGENTE DE ANÁLISIS ---

def crear_agente_pandas():
    df = get_dataframe_cliente()
    if df.empty: return None

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # --- PROMPT ACTUALIZADO PARA MIRAR LA NUEVA COLUMNA ---
    prompt_prefix = """
    Eres un Analista de Datos experto trabajando con un DataFrame de Pandas llamado 'df'.
    
    ### ESTRUCTURA DE DATOS:
    - 'MONTO': Float. Usa esta columna para sumas ($).
    - 'MONEDA': String ('ARS', 'USD', 'EUR'). SIEMPRE agrupa por esta columna.
    - 'FECHA': String. Contiene el texto original (ej: "30-11 al 06-12").
    - 'MESES_IMPACTO': String. Contiene LOS MESES que abarca el evento (ej: "Noviembre, Diciembre").
    
    ### REGLAS DE FILTRADO DE FECHAS (MUY IMPORTANTE):
    1. Si te piden "gastos de Diciembre", NO uses la columna de fecha exacta.
    2. DEBES filtrar usando `df[df['MESES_IMPACTO'].str.contains('Diciembre', case=False, na=False)]`.
    3. Esto es vital porque algunos viajes empiezan en Noviembre pero terminan en Diciembre, y deben contarse.
    
    ### REGLAS GENERALES:
    - Usa `.str.contains` para filtrar texto.
    - Si piden totales, desglosa por moneda (ARS, USD).
    """

    return create_pandas_dataframe_agent(
        llm, 
        df, 
        verbose=True, 
        allow_dangerous_code=True,
        agent_executor_kwargs={"handle_parsing_errors": True},
        prefix=prompt_prefix,
        include_df_in_prompt=True
    )

# --- 3. HERRAMIENTA EXPUESTA ---

@tool
def analista_de_datos_cliente(consulta: str):
    """
    Herramienta AVANZADA de GESTIÓN INTERNA. 
    Especialista en: CÁLCULOS MATEMÁTICOS, sumas de costos, filtros por mes/fecha y reportes financieros.
    """
    try:
        agent = crear_agente_pandas()
        if agent is None: 
            return "Error Técnico: No data."
        
        logger.info(f"📊 Analista procesando: {consulta}")
        response = agent.invoke({"input": consulta})
        output = response.get("output", "")
        
        if not output or "Agent stopped" in output:
            return "Error de Análisis: Intenta reformular la pregunta."
            
        return output

    except Exception as e:
        return f"FALLO EN EL CÁLCULO: {str(e)}"