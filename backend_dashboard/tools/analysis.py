import pandas as pd
import logging
import re
from datetime import datetime
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from tools.dashboard import obtener_datos_sheet_cached, SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID, procesar_fila_cliente

logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DE CAMBIO (COTIZACIÓN REFERENCIA) ---
COTIZACION = {
    "USD": 1200.0,
    "EUR": 1300.0,
    "ARS": 1.0
}

def normalizar_dinero(valor):
    """Detecta moneda y convierte a ARS."""
    if not valor: return 0.0
    val_str = str(valor).strip().upper()
    
    moneda = "ARS"
    if any(s in val_str for s in ["USD", "U$S", "DOLAR", "DÓLAR", "US$"]):
        moneda = "USD"
    elif any(s in val_str for s in ["EUR", "EURO", "€"]):
        moneda = "EUR"
    
    val_limpio = re.sub(r'[^\d.,-]', '', val_str)
    if not val_limpio: return 0.0

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
        return 0.0

    return monto * COTIZACION.get(moneda, 1.0)

def extraer_fecha_inteligente(valor):
    """
    Intenta rescatar una fecha válida de textos sucios como '09 al 12/12' o 'aprox nov 2025'.
    Devuelve un objeto datetime o NaT.
    """
    if not valor: return pd.NaT
    val_str = str(valor).strip()
    
    # 1. Intento directo estándar
    try:
        return pd.to_datetime(val_str, dayfirst=True)
    except:
        pass
    
    # 2. Búsqueda con Regex (Busca patrones dd/mm/aaaa o dd/mm)
    # Busca algo como "12/12" o "12/12/2025"
    match = re.search(r'(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)', val_str)
    if match:
        fecha_texto = match.group(1)
        try:
            # Si es solo "12/12", le agregamos el año actual para que no falle
            if len(fecha_texto) <= 5: 
                fecha_texto += f"/{datetime.now().year}"
            return pd.to_datetime(fecha_texto, dayfirst=True)
        except:
            pass
            
    return pd.NaT

def get_dataframe_cliente():
    raw_data = obtener_datos_sheet_cached(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
    if not raw_data:
        logger.error("❌ DataFrame vacío.")
        return pd.DataFrame()
    
    data_limpia = [procesar_fila_cliente(r) for r in raw_data]
    df = pd.DataFrame(data_limpia)
    
    # 1. Limpieza de Moneda
    if 'COSTO' in df.columns:
        df['COSTO_ORIGINAL'] = df['COSTO']
        df['COSTO'] = df['COSTO'].apply(normalizar_dinero)

    # 2. Limpieza de Fechas (NUEVO: Usando extractor inteligente)
    if 'FECHA' in df.columns:
        df['FECHA_RAW'] = df['FECHA'] # Guardamos original para referencia
        df['FECHA_DT'] = df['FECHA'].apply(extraer_fecha_inteligente)
        
        # Rellenamos fechas inválidas para no perder datos en filtros (opcional, usa fecha hoy o null)
        # df['FECHA_DT'].fillna(pd.Timestamp.now(), inplace=True) 
        
        df['MES'] = df['FECHA_DT'].dt.month
        df['ANIO'] = df['FECHA_DT'].dt.year

    return df

def crear_agente_pandas():
    df = get_dataframe_cliente()
    if df.empty: return None

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    prompt_prefix = f"""
    Eres un experto Financiero del MinCYT. Trabajas con un DataFrame `df`.
    
    IMPORTANTE:
    - La columna 'COSTO' ya está en PESOS ARGENTINOS (ARS). (1 USD = {COTIZACION['USD']} ARS).
    - Para filtrar por fecha, usa 'MES' y 'ANIO'. (Ej: Noviembre 2025 -> MES=11, ANIO=2025).
    - Si 'FECHA_DT' es NaT (Not a Time), esa fila tiene fecha inválida.
    
    TU MISIÓN:
    1. Filtra los datos según lo que pida el usuario.
    2. Suma la columna 'COSTO' de los datos filtrados.
    3. Responde: "Encontré X eventos. El total es $Y pesos".
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
        pasos = response.get("intermediate_steps", [])
        
        debug_info = ""
        if pasos:
            debug_info = "\n\n--- CÁLCULO INTERNO ---\n"
            for action, obs in pasos:
                code = getattr(action, 'tool_input', str(action)).replace("df = df.copy()", "").strip()
                debug_info += f"💻 {code}\n"

        return f"{output}{debug_info}"

    except Exception as e:
        logger.error(f"Error analista: {e}")
        return f"Error de cálculo: {e}"

def steps_summary(steps):
    summary = []
    for action, observation in steps:
        obs_str = str(observation)
        if len(obs_str) > 300: obs_str = obs_str[:300] + "..."
        code = getattr(action, 'tool_input', str(action))
        summary.append((code, obs_str))
    return summary