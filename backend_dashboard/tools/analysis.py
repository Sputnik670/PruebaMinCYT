import pandas as pd
import logging
import re
# import locale  <-- COMENTADO: Ya no dependemos de la configuración regional del servidor
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
# Importamos ambas fuentes (ahora usan la lectura estricta)
from tools.dashboard import get_data_cliente_formatted, get_data_ministerio_formatted

logger = logging.getLogger(__name__)

# Bloque locale comentado para evitar errores en contenedores/render
# try: 
#     locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
# except: 
#     pass

def limpiar_moneda(val):
    """Limpia y convierte strings de dinero a float + moneda."""
    if not val: return 0.0, 'ARS'
    s = str(val).upper().strip()
    
    moneda = 'ARS'
    if 'USD' in s or 'DOLAR' in s: moneda = 'USD'
    elif 'EUR' in s or 'EURO' in s: moneda = 'EUR'
    
    nums = re.sub(r'[^\d.,-]', '', s)
    if not nums: return 0.0, moneda
    
    try:
        if ',' in nums and '.' in nums:
            if nums.rfind(',') > nums.rfind('.'): 
                nums = nums.replace('.', '').replace(',', '.')
            else: 
                nums = nums.replace(',', '')
        elif ',' in nums:
            nums = nums.replace(',', '.')
        elif '.' in nums:
            if nums.count('.') > 1:
                nums = nums.replace('.', '')
            elif re.match(r'^\d{1,3}\.\d{3}$', nums):
                nums = nums.replace('.', '')
            
        return float(nums), moneda
    except Exception as e:
        return 0.0, moneda

def get_df_optimizado():
    """
    Obtiene datos de AMBAS agendas, las unifica y limpia.
    ADAPTADO: Consume la salida estandarizada del nuevo dashboard.py
    y la formatea a las columnas que el agente espera.
    """
    # 1. Obtener datos crudos (Ahora vienen limpios desde dashboard.py)
    data_cliente = get_data_cliente_formatted() or []
    data_ministerio = get_data_ministerio_formatted() or []

    filas_procesadas = []

    # 2. Procesar Agenda Ministerio (Pública)
    # El nuevo dashboard devuelve: FECHA, EVENTO, LUGAR, AMBITO...
    for row in data_ministerio:
        filas_procesadas.append({
            "FECHA_VIAJE": row.get("FECHA", ""),
            "DESTINO": row.get("LUGAR", ""),
            "MOTIVO_EVENTO": row.get("EVENTO", ""),
            "FUNCIONARIO": "Ministerio (Oficial)", # Valor por defecto para diferenciar
            "COSTO_TRASLADO": "0", # Ministerio no tiene costos en tu Excel
            # Mantenemos las etiquetas originales que tu prompt conoce
            "ORIGEN_DATO": "CalendariosInternacionales", 
            "AMBITO": row.get("AMBITO", "No especificado")
        })

    # 3. Procesar Agenda Cliente (Privada)
    # El nuevo dashboard devuelve: FECHA, EVENTO, LUGAR, COSTO...
    for row in data_cliente:
        filas_procesadas.append({
            "FECHA_VIAJE": row.get("FECHA", ""),
            "DESTINO": row.get("LUGAR", ""),
            "MOTIVO_EVENTO": row.get("EVENTO", ""),
            "FUNCIONARIO": row.get("FUNCIONARIO", ""),
            "COSTO_TRASLADO": row.get("COSTO", "0"),
            # Mantenemos las etiquetas originales que tu prompt conoce
            "ORIGEN_DATO": "MisionesOficialesSICyT",
            "AMBITO": "Gestión Interna" # Default si no viene del excel
        })

    # 4. Crear DataFrame Unificado
    if not filas_procesadas: return pd.DataFrame()
    
    df = pd.DataFrame(filas_procesadas)
    
    # 5. Limpieza técnica de nombres de columnas (snake_case)
    # Esto convierte 'FECHA_VIAJE' -> 'fecha_viaje', 'COSTO_TRASLADO' -> 'costo_traslado'
    df.columns = [
        str(c).lower().strip()
        .replace(' ', '_').replace('/', '_').replace('.', '') 
        for c in df.columns
    ]

    # 6. Procesar Dinero (Usando la columna normalizada 'costo_traslado')
    if 'costo_traslado' in df.columns:
        cols = df['costo_traslado'].apply(lambda x: pd.Series(limpiar_moneda(x)))
        df['monto_numerico'] = cols[0]
        df['moneda_detectada'] = cols[1]
    else:
        df['monto_numerico'] = 0.0
        df['moneda_detectada'] = 'ARS'

    # 7. Procesar Fechas (Usando la columna normalizada 'fecha_viaje')
    if 'fecha_viaje' in df.columns:
        # dayfirst=True es clave para fechas argentinas (DD/MM/YYYY)
        df['fecha_dt'] = pd.to_datetime(df['fecha_viaje'], dayfirst=True, errors='coerce')
        
        # Diccionario manual para garantizar nombres en español
        meses_es = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        
        df['mes_numero'] = df['fecha_dt'].dt.month
        df['mes_nombre'] = df['mes_numero'].map(meses_es).fillna("Desconocido")
        df['anio'] = df['fecha_dt'].dt.year
        
    return df.fillna('')

@tool
def analista_de_datos_cliente(consulta: str):
    """
    [DEPARTAMENTO 1: DATOS Y FINANZAS]
    ÚSALA para cálculos o consultas sobre la AGENDA COMPLETA.
    """
    try:
        df = get_df_optimizado()
        if df.empty: 
            return "Error: No hay datos disponibles en ninguna de las agendas."

        llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash-001", temperature=0)
        
        # PROMPT ORIGINAL (INTACTO, solo ajustes de formato visual)
        prefix = f"""
        Eres un Experto Analista de Datos en Python.
        
        ### IMPORTANTE:
        1. **NO CREES DATOS FICTICIOS (MOCK DATA)**.
        2. El DataFrame `df` **YA ESTÁ CARGADO** en tu entorno con los datos reales. ÚSALO DIRECTAMENTE.
        3. No definas `df = pd.DataFrame(...)`. Eso borra los datos reales.

        Trabajas con un DataFrame `df` que combina dos fuentes de datos.
        
        ### CÓMO DIFERENCIAR LOS DATOS (IMPORTANTE):
        - La columna `origen_dato` te dice de dónde viene la información:
            1. **"CalendariosInternacionales"**: Es la agenda pública (eventos, congresos, oficiales).
            2. **"MisionesOficialesSICyT"**: Es la gestión interna (costos, expedientes, misiones).
        
        - La columna `ambito` contiene el alcance geográfico (ej: "Nacional", "Internacional").

        ### COLUMNAS CLAVE:
        - `fecha_dt`: Fecha del evento (tipo datetime).
        - `motivo_evento`: Título o tema.
        - `destino`: Lugar.
        - `monto_numerico`: Costo (float, casi siempre 0 en Calendarios).
        - `ambito`: Alcance del evento.

        ### TUS REGLAS:
        1. Si preguntan por "Oficial", "Internacional" o "Pública", filtra `df[df['origen_dato'] == 'CalendariosInternacionales']`.
        2. Si preguntan "Gastos", "Misiones" o "Gestión", filtra `df[df['origen_dato'] == 'MisionesOficialesSICyT']`.
        3. **SI PIDEN FILTRAR POR ÁMBITO (Nacional/Internacional), usa la columna `ambito`**.
        4. Si preguntan "Comparar" o "Todo", usa todo el dataframe.
        5. Genera código Python/Pandas preciso.

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
        logger.error(f"Error crítico en analista_de_datos: {e}", exc_info=True)
        return f"Hubo un error técnico procesando los datos: {str(e)}"