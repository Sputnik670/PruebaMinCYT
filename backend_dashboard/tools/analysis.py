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
    if not valor: return "ARS", 0.0
    val_str = str(valor).strip().upper()
    moneda = "ARS"
    
    # Detección de moneda
    if any(s in val_str for s in ["USD", "U$S", "DOLAR", "DÓLAR", "US$", "DOLARES"]):
        moneda = "USD"
    elif any(s in val_str for s in ["EUR", "EURO", "€", "EUROS"]):
        moneda = "EUR"
    
    # Limpieza numérica robusta
    val_limpio = re.sub(r'[^\d.,-]', '', val_str)
    if not val_limpio: return moneda, 0.0
    
    # Lógica para diferenciar miles de decimales
    # Si hay punto y coma, asumimos formato estándar (1.000,50 o 1,000.50)
    if ',' in val_limpio and '.' in val_limpio:
        last_comma = val_limpio.rfind(',')
        last_point = val_limpio.rfind('.')
        if last_comma > last_point: # Formato europeo/argentino: 1.000,50
            val_limpio = val_limpio.replace('.', '').replace(',', '.')
        else: # Formato USA: 1,000.50
            val_limpio = val_limpio.replace(',', '')
    elif ',' in val_limpio: 
        # Si solo hay comas, asumimos que es decimal (ej: 50,50)
        val_limpio = val_limpio.replace(',', '.')
        
    try:
        monto = float(val_limpio)
    except ValueError:
        monto = 0.0
    return moneda, monto

def obtener_meses_involucrados(fecha_str):
    """
    Analiza strings como '30-11 al 06-12' y devuelve una lista de nombres de meses.
    Ej: 'Noviembre, Diciembre'
    """
    if not fecha_str: return "Sin Fecha"
    texto = str(fecha_str).lower()
    
    meses_map = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
        7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    
    # Buscar patrones dd/mm
    matches = re.findall(r'(\d{1,2})[/-](\d{1,2})', texto)
    meses_detectados = set()
    
    for dia, mes in matches:
        try:
            m = int(mes)
            if 1 <= m <= 12:
                meses_detectados.add(meses_map[m])
        except: pass

    # Intento fallback con pandas para fechas únicas
    try:
        dt = pd.to_datetime(fecha_str, dayfirst=True)
        if not pd.isna(dt):
            meses_detectados.add(meses_map[dt.month])
    except: pass

    if not meses_detectados:
        return "Fecha Desconocida"
        
    return ", ".join(sorted(list(meses_detectados)))

def extraer_fecha_inteligente(valor):
    """Intenta obtener un objeto datetime válido para ordenamientos."""
    if not valor: return pd.NaT
    val_str = str(valor).strip()
    
    # Prioridad: Buscar la primera fecha en el texto
    match = re.search(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', val_str)
    if match:
        try:
            dia, mes = match.group(1), match.group(2)
            anio = match.group(3)
            if not anio: anio = datetime.now().year
            return pd.to_datetime(f"{dia}/{mes}/{anio}", dayfirst=True)
        except: pass
            
    try:
        return pd.to_datetime(val_str, dayfirst=True)
    except:
        return pd.NaT

def get_dataframe_cliente():
    """Construye el DataFrame maestro con datos limpios y tipados."""
    try:
        raw_data = obtener_datos_sheet_cached(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
        if not raw_data:
            return pd.DataFrame()
        
        data_limpia = [procesar_fila_cliente(r) for r in raw_data]
        df = pd.DataFrame(data_limpia)
        
        # Procesamiento de Costos (Si existe la columna)
        col_costo = next((c for c in df.columns if 'COSTO' in c.upper() or 'PRECIO' in c.upper()), None)
        if col_costo:
            parsed = df[col_costo].apply(parse_money_value)
            df['MONEDA'] = parsed.apply(lambda x: x[0])
            df['MONTO'] = parsed.apply(lambda x: x[1]).astype(float)

        # Procesamiento de Fechas
        col_fecha = next((c for c in df.columns if 'FECHA' in c.upper()), None)
        if col_fecha:
            df['FECHA_DT'] = df[col_fecha].apply(extraer_fecha_inteligente)
            df['MESES_IMPACTO'] = df[col_fecha].apply(obtener_meses_involucrados)

        return df
    except Exception as e:
        logger.error(f"Error construyendo DataFrame: {e}")
        return pd.DataFrame()

# --- 2. CONFIGURACIÓN DEL AGENTE DE ANÁLISIS ---

def crear_agente_pandas():
    df = get_dataframe_cliente()
    if df.empty: return None

    # USAMOS EL MODELO MÁS POTENTE DISPONIBLE EN TU LISTA
    llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash-exp", temperature=0)
    
    # --- PROMPT CON EJEMPLOS (FEW-SHOT) ---
    prompt_prefix = """
    Eres un Analista de Datos experto. Trabajas con un DataFrame de Pandas 'df'.
    
    ### DICCIONARIO DE DATOS:
    - 'MONTO': (float) El valor numérico del costo. ÚSALA PARA SUMAS Y PROMEDIOS.
    - 'MONEDA': (str) 'ARS', 'USD' o 'EUR'. SIEMPRE agrupa por esta columna antes de sumar.
    - 'FECHA': (str) Texto original (ej: "30-11 al 06-12").
    - 'MESES_IMPACTO': (str) Meses textuales (ej: "Noviembre, Diciembre"). USA ESTA PARA FILTRAR POR MES.
    - 'LUGAR': (str) Ciudad o destino.
    - 'MOTIVO / EVENTO': (str) Descripción de la actividad.

    ### EJEMPLOS DE RAZONAMIENTO (Sigue estos patrones):
    
    Caso 1: "Gastos totales en dólares"
    Código: df[df['MONEDA'] == 'USD']['MONTO'].sum()
    
    Caso 2: "Cuánto se gastó en viajes a Córdoba"
    Código: df[df['LUGAR'].str.contains('Córdoba', case=False, na=False)]['MONTO'].sum()
    
    Caso 3: "Gastos de Noviembre"
    Código: df[df['MESES_IMPACTO'].str.contains('Noviembre', case=False, na=False)].groupby('MONEDA')['MONTO'].sum()
    
    Caso 4: "Listar los eventos de Inteligencia Artificial"
    Código: df[df['MOTIVO / EVENTO'].str.contains('Inteligencia|IA', case=False, na=False, regex=True)][['FECHA', 'MOTIVO / EVENTO']]

    ### REGLAS OBLIGATORIAS:
    1. Usa SIEMPRE `.str.contains(..., case=False, na=False)` para búsquedas de texto (insensible a mayúsculas).
    2. Si piden totales monetarios, devuelve el número separado por moneda (ej: "1000 USD y 50000 ARS"). NO sumes monedas distintas.
    3. Si el resultado es vacío, dilo claramente.
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
    Herramienta PRINCIPAL para preguntas sobre COSTOS, FECHAS, LUGARES y ESTADÍSTICAS de la agenda.
    Úsala cuando el usuario pregunte: "¿Cuánto gastamos?", "¿Cuántos viajes hubo?", "Detalle de tal evento".
    """
    try:
        agent = crear_agente_pandas()
        if agent is None: 
            return "Error Técnico: No se pudieron cargar los datos para el análisis."
        
        logger.info(f"📊 Analista procesando: {consulta}")
        
        # Invocación del agente
        response = agent.invoke({"input": consulta})
        output = response.get("output", "")
        
        if not output or "Agent stopped" in output:
            return "No pude realizar el cálculo exacto. Por favor, sé más específico con la pregunta."
            
        return output

    except Exception as e:
        logger.error(f"Error en analista: {e}")
        return f"Ocurrió un error técnico al procesar los datos: {str(e)}"