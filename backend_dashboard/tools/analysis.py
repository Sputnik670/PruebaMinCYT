import pandas as pd
import logging
import re
import locale
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
# Asumo que esta importación funciona en tu entorno local
from tools.dashboard import get_data_cliente_formatted

logger = logging.getLogger(__name__)

# Configuración de locale para fechas en español (ayuda a pandas)
try: 
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except: 
    pass

def limpiar_moneda(val):
    """
    Limpia y convierte strings de dinero a float + moneda.
    Maneja formatos: '$ 1.200,50', 'USD 1,000', '1.000.000' (miles con punto).
    """
    if not val: return 0.0, 'ARS'
    s = str(val).upper().strip()
    
    # 1. Detectar moneda
    moneda = 'ARS'
    if 'USD' in s or 'DOLAR' in s: moneda = 'USD'
    elif 'EUR' in s or 'EURO' in s: moneda = 'EUR'
    
    # 2. Limpieza preliminar: quitar letras y espacios, dejar solo números, puntos, comas y guiones
    nums = re.sub(r'[^\d.,-]', '', s)
    if not nums: return 0.0, moneda
    
    try:
        # LÓGICA ROBUSTA PARA FORMATO LATINO/EUROPEO (1.000,00) vs USA (1,000.00)
        
        # Caso A: Tiene ambos (1.000,50 o 1,000.50)
        if ',' in nums and '.' in nums:
            if nums.rfind(',') > nums.rfind('.'): 
                # Formato Latino: 1.000,50 -> Quitar punto miles, cambiar coma a punto
                nums = nums.replace('.', '').replace(',', '.')
            else: 
                # Formato USA: 1,000.50 -> Quitar coma miles
                nums = nums.replace(',', '')
                
        # Caso B: Solo tiene coma (100,50 o 100,000 -> asumiendo decimal si es formato corto)
        elif ',' in nums:
            # Asumimos formato latino decimal: 500,50 -> 500.50
            nums = nums.replace(',', '.')
            
        # Caso C: Solo tiene punto (1.000 o 100.50)
        elif '.' in nums:
            # Si tiene más de un punto (1.000.000), son miles -> quitar todos
            if nums.count('.') > 1:
                nums = nums.replace('.', '')
            # Si tiene un solo punto, es ambiguo. 
            # Regla de negocio MinCYT: Si tiene 3 decimales exactos (1.000), suele ser mil.
            # Pero Python float("1.000") es 1.0. 
            # Decisión segura: Si parece formato de miles (dígito.3dígitos), quitar punto.
            elif re.match(r'^\d{1,3}\.\d{3}$', nums):
                nums = nums.replace('.', '')
            
        return float(nums), moneda
    except Exception as e:
        logger.warning(f"Error parseando moneda '{val}': {e}")
        return 0.0, moneda

def get_df_optimizado():
    """Obtiene los datos crudos y devuelve un DataFrame limpio y tipado para la IA."""
    data = get_data_cliente_formatted()
    if not data: return pd.DataFrame()
    
    df = pd.DataFrame(data)
    
    # 1. Normalizar nombres de columnas (snake_case para facilitar al código de la IA)
    df.columns = [
        str(c).lower().strip()
        .replace(' ', '_').replace('/', '_').replace('.', '') 
        for c in df.columns
    ]
    # Esperamos columnas como: 'fecha_viaje', 'costo_traslado', 'motivo_evento', 'destino'

    # 2. Procesar Dinero (Crea columnas numéricas reales)
    if 'costo_traslado' in df.columns:
        cols = df['costo_traslado'].apply(lambda x: pd.Series(limpiar_moneda(x)))
        df['monto_numerico'] = cols[0]
        df['moneda_detectada'] = cols[1]
    else:
        df['monto_numerico'] = 0.0
        df['moneda_detectada'] = 'ARS'

    # 3. Procesar Fechas (CRÍTICO para filtros "mes pasado", "2024", etc)
    if 'fecha_viaje' in df.columns:
        # dayfirst=True es clave para fechas latinas (DD/MM/YYYY)
        df['fecha_dt'] = pd.to_datetime(df['fecha_viaje'], dayfirst=True, errors='coerce')
        
        # Eliminamos filas donde la fecha no se pudo parsear (NaT) para no romper el agente
        # Opcional: podrías dejarlas, pero mejor limpiar para cálculos de tiempo
        
        # Creamos columnas auxiliares explícitas para facilitar el filtrado al LLM
        df['mes_nombre'] = df['fecha_dt'].dt.month_name(locale='es_ES.UTF-8' if locale.getlocale()[0] else None)
        df['mes_numero'] = df['fecha_dt'].dt.month
        df['anio'] = df['fecha_dt'].dt.year
        
    return df.fillna('')

@tool
def analista_de_datos_cliente(consulta: str):
    """
    [DEPARTAMENTO 1: DATOS Y FINANZAS]
    ÚSALA EXCLUSIVAMENTE para cálculos matemáticos, financieros o fechas exactas sobre la "Gestión Interna".
    - Sumar gastos, calcular promedios, buscar montos específicos.
    - Filtrar por fechas exactas (meses, años) o destinos.
    - NO la uses para preguntas generales o texto cualitativo.
    """
    try:
        df = get_df_optimizado()
        if df.empty: 
            return "Error: No hay datos disponibles en la tabla de Gestión Interna o no se pudo cargar."

        # Usamos temperatura 0 para máxima precisión en generación de código Python
        llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash-001", temperature=0)
        
        prefix = f"""
        Eres un Experto Analista de Datos en Python (Pandas). 
        Trabajas con un DataFrame `df` que contiene {len(df)} registros de la "Gestión Interna" del MinCYT.

        ### ESTRUCTURA DEL DATAFRAME:
        - `numero_expediente`: Código del trámite.
        - `funcionario`: Persona que viaja o solicita.
        - `destino`: Lugar del evento.
        - `motivo_evento`: Descripción del tema.
        - `monto_numerico` (Float): EL VALOR REAL PARA SUMAR. ÚSALO SIEMPRE PARA CÁLCULOS.
        - `moneda_detectada`: (ARS, USD, EUR). ¡IMPORTANTE: NO SUMES MONEDAS DISTINTAS! Agrupa por esta columna.
        - `fecha_dt` (Datetime): Objeto fecha real.
        - `mes_numero` (1-12) y `anio` (Int): Útiles para filtrar.

        ### TUS REGLAS DE ORO:
        1. **PYTHON REAL**: Genera código pandas para resolver la consulta. No adivines.
        2. **MONEDA**: Si piden totales, agrupa siempre por `moneda_detectada`. Ejemplo: "Total: 100 USD y 5000 ARS".
        3. **TEXTO**: Para búsquedas de texto (ej: "viajes nucleares"), usa `df[df['motivo_evento'].str.contains('nucleares', case=False, na=False)]`.
        4. **SIN DATOS**: Si el filtro devuelve vacío, di "No se encontraron registros que coincidan".
        5. **EXPLICACIÓN**: Al final, explica brevemente el resultado ("El gasto total en mayo fue de...").

        Pregunta del usuario: {consulta}
        """

        agent = create_pandas_dataframe_agent(
            llm, 
            df, 
            verbose=True, 
            allow_dangerous_code=True, # Necesario para ejecutar Python
            agent_executor_kwargs={"handle_parsing_errors": True},
            prefix=prefix,
            include_df_in_prompt=False, # False para ahorrar tokens, ya describimos las columnas
            number_of_head_rows=5
        )
        
        # Ejecución
        resultado = agent.invoke({"input": consulta})
        return resultado["output"]

    except Exception as e:
        logger.error(f"Error crítico en analista_de_datos: {e}", exc_info=True)
        return f"Hubo un error técnico procesando los datos: {str(e)}"