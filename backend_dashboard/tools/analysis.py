import pandas as pd
import logging
from datetime import datetime
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from tools.dashboard import get_data_cliente_formatted, get_data_ministerio_formatted

logger = logging.getLogger(__name__)

def get_df_optimizado():
    """
    Obtiene datos de SQL y genera un DataFrame unificado.
    """
    data_cliente = get_data_cliente_formatted() or []
    data_ministerio = get_data_ministerio_formatted() or []
    
    todos_los_datos = data_cliente + data_ministerio
    
    if not todos_los_datos: 
        return pd.DataFrame()
    
    df = pd.DataFrame(todos_los_datos)
    
    # Conversión estricta de tipos para que Pandas funcione bien
    if 'fecha' in df.columns:
        df['fecha'] = pd.to_datetime(df['fecha'])
    if 'fecha_fin' in df.columns:
        df['fecha_fin'] = pd.to_datetime(df['fecha_fin'])
    if 'costo' in df.columns:
        df['costo'] = pd.to_numeric(df['costo'], errors='coerce').fillna(0)
        
    # Rellenar nulos con valores seguros para evitar crashes
    df = df.fillna({
        'titulo': 'Sin título',
        'lugar': 'Desconocido',
        'moneda': 'ARS',
        'funcionario': 'No asignado'
    })
    
    return df

@tool
def analista_de_datos_cliente(consulta: str):
    """
    [DEPARTAMENTO DE DATOS]
    Motor de análisis inteligente sobre SQL. 
    Capaz de calcular costos por moneda, duraciones de viajes y filtrar por agenda.
    """
    try:
        df = get_df_optimizado()
        if df.empty: 
            return "Error: La base de datos está vacía."

        # LLM Temperatura 0 para lógica matemática estricta
        llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash-001", temperature=0)
        
        # Contexto temporal dinámico
        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        
        # --- PROMPT DINÁMICO & CIENTÍFICO (SCHEMA-AWARE) ---
        prefix = f"""
        Eres un Analista de Datos Forense (Data Scientist Senior).
        HOY ES: {fecha_actual}.

        ### 🧬 TU CEREBRO (DATAFRAME `df`):
        - `fecha` (datetime): Inicio del evento.
        - `fecha_fin` (datetime): Fin del evento (puede ser NaT si es de 1 día).
        - `titulo`, `lugar`, `funcionario` (strings).
        - `costo` (float): Valor numérico exacto.
        - `moneda` (string): Divisa ('USD', 'EUR', 'ARS').
        - `origen_dato`: 'MisionesOficiales' (Gastos) o 'CalendarioPublico'.

        ### ⚠️ PROTOCOLO DE SEGURIDAD (ANTI-ALUCINACIÓN):
        1. **BÚSQUEDA EXACTA:** - Usa `str.contains(..., case=False, na=False)` para buscar texto.
           - Si el usuario dice "Londres", busca en `lugar` Y en `titulo`.
        
        2. **VERIFICACIÓN DE VACÍO (CRÍTICO):**
           - Antes de responder, revisa si tu filtro devolvió 0 filas.
           - SI ES 0: Responde LITERALMENTE: "No encontré registros que coincidan con [término] en la base de datos".
           - PROHIBIDO INVENTAR DATOS. Si no está, no está.

        ### 📐 REGLAS DE OPERACIÓN:
        
        1. **MULTIMONEDA:** - NUNCA sumes la columna `costo` directamente sin agrupar.
           - SIEMPRE agrupa por moneda: `df.groupby('moneda')['costo'].sum()`.
           - Reporta totales separados (ej: "100 USD y 5000 ARS").

        2. **DURACIÓN Y FECHAS:**
           - La duración es `(df['fecha_fin'] - df['fecha']).dt.days + 1`.
           - Si preguntan "¿Cuándo termina?", usa `fecha_fin`.
           - Si preguntan por "Próximos viajes", filtra `df['fecha'] >= '{fecha_actual}'`.
        
        3. **RESPUESTA:**
           - Sé conciso y directo con los números.

        Pregunta del usuario: {consulta}
        """

        agent = create_pandas_dataframe_agent(
            llm, 
            df, 
            verbose=True, 
            allow_dangerous_code=True,
            agent_executor_kwargs={"handle_parsing_errors": True},
            prefix=prefix,
            include_df_in_prompt=False, # No pasamos las filas, solo la estructura
            number_of_head_rows=3
        )
        
        resultado = agent.invoke({"input": consulta})
        return resultado["output"]

    except Exception as e:
        logger.error(f"Error en analista: {e}", exc_info=True)
        return "Error técnico procesando datos. Intenta ser más específico."