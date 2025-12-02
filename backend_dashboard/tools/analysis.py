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

# 1. FUNCIÓN DE LIMPIEZA DE MONEDA (parse_money_value)
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

# 2. FUNCIÓN DE EXTRACCIÓN DE FECHA (extraer_fecha_inteligente)
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
    
# 3. FUNCIÓN QUE CONSTRUYE EL DATAFRAME (get_dataframe_cliente)
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
        
        # Aseguramos que MONTO sea float para cálculos
        df['MONTO'] = df['MONTO'].astype(float)

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
    
    # --- PROMPT EXPANDIDO CON REGLAS DE NEGOCIO ---
    prompt_prefix = """
    Estás trabajando con un DataFrame de Pandas 'df'.
    
    1. CONTEXTO GENERAL:
       - Este 'df' contiene la 'Agenda de Gestión Interna'.
       - Si preguntan por "total", "agenda" o "gestión interna" a secas -> USA TODAS LAS FILAS (no filtres).

    2. MAPEO DE COLUMNAS (Diccionario de Negocio):
       - Si preguntan por "Institución" u "Organismo" -> Usa la columna 'INSTITUCIÓN'.
       - Si preguntan por "Destino", "Ciudad" o "Viajes a..." -> Usa la columna 'LUGAR'.
       - Si preguntan por "Estado" o "Pendientes" -> Usa la columna 'ESTADO' o 'RENDICIÓN'.
       - Si preguntan por "Fecha" o "Mes" -> Usa las columnas 'MES' y 'ANIO'.

    3. REGLAS DE FILTRADO INTELIGENTE:
       - Filtro por TEXTO (Lugar/Evento/Institución): Usa siempre `str.contains('texto', case=False, na=False)`.
       - Filtro por FECHA: Si piden "marzo", filtra `df['MES'] == 3`.
       - Filtro por MONEDA: Siempre agrupa los resultados finales por 'MONEDA'.

    4. FORMATO DE SALIDA OBLIGATORIO:
       - Responde EXACTAMENTE con este formato para los totales:
         "el costo es = EURO: X Y DOLAR: Y Y PESOS: Z"
       - Si el usuario pidió un detalle (ej: "lista de viajes"), puedes listar las primeras 5 filas antes del total.
    """

    return create_pandas_dataframe_agent(
        llm, 
        df, 
        verbose=True, 
        allow_dangerous_code=True,
        return_intermediate_steps=False,
        prefix=prompt_prefix,
        # Pasamos el parámetro DENTRO de agent_executor_kwargs para evitar el UserWarning
        agent_executor_kwargs={"handle_parsing_errors": True}
    )

@tool
def analista_de_datos_cliente(consulta: str):
    """
    Herramienta AVANZADA de GESTIÓN INTERNA. 
    Especialista en: CÁLCULOS MATEMÁTICOS, sumas de costos, filtros complejos (por mes, por moneda, por estado) y reportes financieros.
    Usa esta herramienta si la pregunta requiere procesar números o filtrar la agenda interna con precisión.
    """
    try:
        agent = crear_agente_pandas()
        if not agent: return "Error: No hay datos disponibles en la planilla."
        
        response = agent.invoke({"input": consulta})
        
        # Devolvemos solo el output final para el usuario.
        return response.get("output", f"Error: El agente no pudo generar una respuesta para '{consulta}'.")

    except Exception as e:
        logger.error(f"Error analista: {e}")
        # Si falla incluso con el manejo de errores, devolvemos un mensaje amigable
        return f"Error de cálculo (intenta reformular): {e}"