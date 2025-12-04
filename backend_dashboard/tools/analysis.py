import pandas as pd
import logging
import re
import locale
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from tools.dashboard import get_data_cliente_formatted

logger = logging.getLogger(__name__)

# Intentamos configurar locale para fechas en español (ayuda a pandas a entender "dic", "enero", etc)
try: locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except: pass

def limpiar_moneda(val):
    """Convierte '$ 1.200,50' o 'USD 1,000' en float 1200.50 y extrae la moneda"""
    if not val: return 0.0, 'ARS'
    s = str(val).upper().strip()
    
    moneda = 'ARS'
    if 'USD' in s or 'DOLAR' in s: moneda = 'USD'
    elif 'EUR' in s or 'EURO' in s: moneda = 'EUR'
    
    # Dejar solo números, puntos y comas
    nums = re.sub(r'[^\d.,-]', '', s)
    if not nums: return 0.0, moneda
    
    try:
        # Lógica para detectar formato europeo/latino (1.000,00) vs gringo (1,000.00)
        if ',' in nums and '.' in nums:
            if nums.rfind(',') > nums.rfind('.'): # Caso 1.000,50
                nums = nums.replace('.', '').replace(',', '.')
            else: # Caso 1,000.50
                nums = nums.replace(',', '')
        elif ',' in nums: 
            nums = nums.replace(',', '.')
            
        return float(nums), moneda
    except:
        return 0.0, moneda

def get_df_optimizado():
    data = get_data_cliente_formatted()
    if not data: return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # 1. Normalizar nombres de columnas (snake_case para facilitar al código)
    df.columns = [
        str(c).lower().strip()
        .replace(' ', '_').replace('/', '_').replace('.', '') 
        for c in df.columns
    ]
    # Mapeo típico: 'fecha_viaje', 'costo_traslado', 'motivo_evento', 'destino'

    # 2. Procesar Dinero
    if 'costo_traslado' in df.columns:
        cols = df['costo_traslado'].apply(lambda x: pd.Series(limpiar_moneda(x)))
        df['monto_numerico'] = cols[0]
        df['moneda_detectada'] = cols[1]
    else:
        df['monto_numerico'] = 0.0
        df['moneda_detectada'] = 'ARS'

    # 3. Procesar Fechas (CRÍTICO)
    if 'fecha_viaje' in df.columns:
        # dayfirst=True es clave para fechas latinas (DD/MM/YYYY)
        df['fecha_dt'] = pd.to_datetime(df['fecha_viaje'], dayfirst=True, errors='coerce')
        # Creamos columnas auxiliares para facilitar el filtrado al LLM
        df['mes_nombre'] = df['fecha_dt'].dt.month_name(locale='es_ES.UTF-8' if locale.getlocale()[0] else None)
        df['mes_numero'] = df['fecha_dt'].dt.month
        df['anio'] = df['fecha_dt'].dt.year

    return df.fillna('')

@tool
def analista_de_datos_cliente(consulta: str):
    """
    ÚSALA para responder sobre:
    - Gastos, Costos, Presupuesto (en ARS, USD, EUR).
    - Fechas, Meses (ej: "gastos de diciembre").
    - Expedientes, Funcionarios, Destinos.
    - Esta herramienta tiene los datos de 'Gestión Interna'.
    """
    try:
        df = get_df_optimizado()
        if df.empty: return "Error: No hay datos disponibles en la tabla de Gestión Interna."

        llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash-001", temperature=0)
        
        prefix = f"""
        Eres un Experto en Datos. Analizas un DataFrame `df` con {len(df)} registros.
        ESTOS DATOS CORRESPONDEN A LA "GESTIÓN INTERNA" o "AGENDA DEL CLIENTE".

        ### COLUMNAS DISPONIBLES:
        - `numero_expediente`: Código del trámite.
        - `funcionario`: Nombre del viajero.
        - `destino`: Lugar.
        - `monto_numerico` (Float): EL VALOR REAL PARA SUMAR. ÚSALO SIEMPRE.
        - `moneda_detectada`: Agrupa por esto (ARS, USD, EUR). ¡NO SUMES MONEDAS DISTINTAS!
        - `fecha_dt` (Datetime): Fecha real.
        - `mes_numero` (Int): 1 a 12. Úsalo para filtrar (ej: Diciembre = 12).
        
        ### REGLAS DE ORO:
        1. **FECHAS**: Si piden "Diciembre", filtra: `df[df['mes_numero'] == 12]`. Si piden "mes pasado", calcula relativo a hoy.
        2. **DINERO**: Para "gastos totales", agrupa: `df.groupby('moneda_detectada')['monto_numerico'].sum()`.
        3. **GESTIÓN INTERNA**: Si el usuario pregunta por "datos de gestión interna", SE REFIERE A ESTE DATAFRAME. Responde directamente.
        4. **SIN HALLAZGOS**: Si el filtro da vacío, di "No hay registros para esa fecha/criterio". No inventes.

        Pregunta: {consulta}
        """

        agent = create_pandas_dataframe_agent(
            llm, df, verbose=True, allow_dangerous_code=True,
            agent_executor_kwargs={"handle_parsing_errors": True},
            prefix=prefix,
            include_df_in_prompt=None 
        )
        return agent.invoke({"input": consulta})["output"]

    except Exception as e:
        logger.error(f"Error analista: {e}")
        return f"Error procesando datos: {str(e)}"