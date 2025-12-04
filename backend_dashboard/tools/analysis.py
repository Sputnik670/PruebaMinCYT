import pandas as pd
import logging
import re
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from tools.dashboard import get_data_cliente_formatted

logger = logging.getLogger(__name__)

def parse_money(val):
    if not val: return 0.0
    s = str(val).upper().strip()
    nums = re.sub(r'[^\d.,-]', '', s)
    if not nums: return 0.0
    if ',' in nums and '.' in nums:
        if nums.rfind(',') > nums.rfind('.'): nums = nums.replace('.', '').replace(',', '.')
        else: nums = nums.replace(',', '')
    elif ',' in nums: nums = nums.replace(',', '.')
    try: return float(nums)
    except: return 0.0

def get_df():
    data = get_data_cliente_formatted()
    if not data: return pd.DataFrame()
    df = pd.DataFrame(data)
    
    if 'COSTO_TRASLADO' in df.columns:
        df['MONTO'] = df['COSTO_TRASLADO'].apply(parse_money)
        df['MONEDA'] = df['COSTO_TRASLADO'].apply(lambda x: 'USD' if 'USD' in str(x).upper() else ('EUR' if 'EUR' in str(x).upper() else 'ARS'))
    
    return df

def crear_agente():
    df = get_df()
    if df.empty: return None
    
    # Modelo 2.0 Flash estable
    llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash-001", temperature=0)
    
    prompt = """
    Eres un analista de gestión. Trabajas con un DataFrame 'df' de Misiones Oficiales.
    
    ### TUS COLUMNAS (NO INVENTES OTRAS):
    - 'NUMERO_EXPEDIENTE': El código del Expediente (ej: EX-2025...). Úsala para 'expediente' o 'EE'.
    - 'FUNCIONARIO': Nombre de quien viajó.
    - 'DESTINO': Lugar del viaje.
    - 'FECHA_VIAJE': Fecha.
    - 'MOTIVO_EVENTO': Descripción.
    - 'MONTO' y 'MONEDA': Para costos.
    - 'ESTADO_TRAMITE': Estado actual (ej: 'RENDICIÓN PENDIENTE').
    - 'RENDICION': Detalles de la rendición.

    ### INSTRUCCIONES OBLIGATORIAS:
    1. Si piden "Expediente de [Lugar]", FILTRA por DESTINO y MUESTRA 'NUMERO_EXPEDIENTE'.
       Código: df[df['DESTINO'].str.contains('Lugar', case=False, na=False)][['NUMERO_EXPEDIENTE', 'FUNCIONARIO']].to_string()
       
    2. Si piden "Quién viajó a [Lugar]", FILTRA por DESTINO y MUESTRA 'FUNCIONARIO'.
    
    3. Si piden "Estado" o "Rendición", usa las columnas 'ESTADO_TRAMITE' y 'RENDICION'.
    
    Si la celda del expediente dice 'No especificado' o está vacía, dilo claramente.
    """
    
    return create_pandas_dataframe_agent(
        llm, df, verbose=True, allow_dangerous_code=True,
        agent_executor_kwargs={"handle_parsing_errors": True},
        prefix=prompt
    )

@tool
def analista_de_datos_cliente(consulta: str):
    """
    ÚSALA SIEMPRE para: Expedientes (EE), Costos, Funcionarios, Destinos, Estados.
    """
    try:
        agent = crear_agente()
        if not agent: return "Error: Sin datos."
        return agent.invoke({"input": consulta})["output"]
    except Exception as e:
        return f"Error: {str(e)}"