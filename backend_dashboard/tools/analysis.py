import pandas as pd
import logging
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from tools.dashboard import get_data_cliente_formatted, get_data_ministerio_formatted

logger = logging.getLogger(__name__)

def get_df_optimizado():
    """
    Obtiene datos de SQL y genera un DataFrame unificado y limpio.
    """
    data_cliente = get_data_cliente_formatted() or []
    data_ministerio = get_data_ministerio_formatted() or []
    
    todos_los_datos = data_cliente + data_ministerio
    
    if not todos_los_datos: 
        return pd.DataFrame()
    
    df = pd.DataFrame(todos_los_datos)
    
    # Ajustes de tipos
    if 'fecha' in df.columns:
        df['fecha'] = pd.to_datetime(df['fecha'])
        
    # Rellenar nulos
    df = df.fillna('')
    
    return df

@tool
def analista_de_datos_cliente(consulta: str):
    """
    [DEPARTAMENTO DE DATOS]
    Úsalo para responder preguntas sobre la AGENDA, VIAJES, FUNCIONARIOS, COSTOS o FECHAS.
    Tiene acceso a toda la base de datos unificada (SQL).
    """
    try:
        df = get_df_optimizado()
        if df.empty: 
            return "Error: La base de datos está vacía. No puedo consultar nada."

        # Modelo Flash con temperatura 0 para análisis estricto
        llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash-001", temperature=0)
        
        # --- PROMPT MAESTRO DE ANÁLISIS DE DATOS ---
        prefix = f"""
        Eres el Analista de Datos Principal del MinCYT. 
        Tu trabajo es programar en Python (Pandas) para extraer LA VERDAD exacta del DataFrame `df`.

        ### 🧠 TU CEREBRO (DATAFRAME `df`):
        Las columnas disponibles son:
        - `fecha` (datetime): Cuándo ocurre.
        - `titulo` (string): Nombre del evento o motivo.
        - `lugar` (string): Ciudad, País o Destino.
        - `funcionario` (string): Persona que viaja.
        - `costo` (float): El número del dinero gastado.
        - `moneda` (string): 'ARS', 'USD', 'EUR'.
        - `origen_dato`: 'MisionesOficiales' (Gastos) o 'CalendarioPublico' (Agenda).

        ### 🔎 ESTRATEGIA DE BÚSQUEDA (IMPORTANTE):
        1. **BÚSQUEDA CRUZADA:** Si el usuario menciona un nombre (ej: "Londres", "Pérez", "Congreso"), NO busques solo en una columna.
           - Código sugerido: `df[df['titulo'].str.contains('Term', case=False) | df['lugar'].str.contains('Term', case=False) | df['funcionario'].str.contains('Term', case=False)]`
        
        2. **PREGUNTAS DE "MÁS CARO":**
           - Ordena por `costo` descendente: `df.sort_values(by='costo', ascending=False).head(1)`.
           - ¡OJO! Menciona siempre la MONEDA. 100 USD > 1000 ARS.

        3. **FECHAS:** - Si piden "¿Cuándo fue?", devuelve la columna `fecha` formateada como string.

        4. **ANTI-ALUCINACIÓN:** - Si el filtro devuelve 0 filas, RESPONDE: "No encontré datos sobre eso en la tabla".
           - NO inventes fechas ni costos. Muestra solo lo que ves.

        Pregunta del usuario: {consulta}
        """

        agent = create_pandas_dataframe_agent(
            llm, 
            df, 
            verbose=True, 
            allow_dangerous_code=True,
            agent_executor_kwargs={"handle_parsing_errors": True},
            prefix=prefix,
            include_df_in_prompt=False,
            number_of_head_rows=5
        )
        
        resultado = agent.invoke({"input": consulta})
        return resultado["output"]

    except Exception as e:
        logger.error(f"Error en analista: {e}", exc_info=True)
        return "Hubo un error técnico al leer los datos. Intenta reformular."