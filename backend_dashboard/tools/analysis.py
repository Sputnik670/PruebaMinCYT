import pandas as pd
import logging
import re
import traceback
from datetime import datetime
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool
from tools.dashboard import obtener_datos_sheet_cached, SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID, procesar_fila_cliente

logger = logging.getLogger(__name__)

# --- 1. FUNCIONES DE LIMPIEZA Y PREPARACIÓN (ETL) ---

def parse_money_value(valor):
    """
    Convierte strings de dinero sucios (ej: '$ 1.200,50') a tuplas (Moneda, Float).
    Maneja errores de formato comunes en Excel.
    """
    if not valor: return "ARS", 0.0
    val_str = str(valor).strip().upper()
    
    # Detección de moneda
    moneda = "ARS"
    if any(s in val_str for s in ["USD", "U$S", "DOLAR", "DÓLAR", "US$", "DOLARES"]):
        moneda = "USD"
    elif any(s in val_str for s in ["EUR", "EURO", "€", "EUROS"]):
        moneda = "EUR"
    
    # Limpieza numérica: Dejar solo dígitos, puntos, comas y guiones
    val_limpio = re.sub(r'[^\d.,-]', '', val_str)
    if not val_limpio: return moneda, 0.0

    # Lógica heurística para decimales (detectar si es 1.000,00 o 1,000.00)
    if ',' in val_limpio and '.' in val_limpio:
        last_comma = val_limpio.rfind(',')
        last_point = val_limpio.rfind('.')
        if last_comma > last_point: # Formato Europeo/Latam: 1.000,50
            val_limpio = val_limpio.replace('.', '').replace(',', '.')
        else: # Formato US: 1,000.50
            val_limpio = val_limpio.replace(',', '')
    elif ',' in val_limpio:
        # Asumimos coma como decimal si no hay puntos (ej: 500,50 -> 500.50)
        val_limpio = val_limpio.replace(',', '.')
    
    try:
        monto = float(val_limpio)
    except ValueError:
        monto = 0.0
        
    return moneda, monto

def extraer_fecha_inteligente(valor):
    """Intenta parsear fechas en múltiples formatos."""
    if not valor: return pd.NaT
    val_str = str(valor).strip()
    
    # Intento 1: Parseo directo (pandas es inteligente)
    # Forzamos dayfirst=True para formato Latino (DD/MM/YYYY)
    try:
        return pd.to_datetime(val_str, dayfirst=True)
    except:
        pass
        
    # Intento 2: Regex para extraer DD/MM
    match = re.search(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?', val_str)
    if match:
        try:
            dia, mes = match.group(1), match.group(2)
            anio = match.group(3)
            if not anio: anio = datetime.now().year
            return pd.to_datetime(f"{dia}/{mes}/{anio}", dayfirst=True)
        except:
            pass
    return pd.NaT

def get_dataframe_cliente():
    """Construye el DataFrame maestro con datos limpios y columnas auxiliares."""
    try:
        raw_data = obtener_datos_sheet_cached(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
        if not raw_data:
            return pd.DataFrame()
        
        data_limpia = [procesar_fila_cliente(r) for r in raw_data]
        df = pd.DataFrame(data_limpia)
        
        # Enriquecimiento de Datos (Feature Engineering para la IA)
        if 'COSTO' in df.columns:
            parsed = df['COSTO'].apply(parse_money_value)
            df['MONEDA'] = parsed.apply(lambda x: x[0])
            df['MONTO'] = parsed.apply(lambda x: x[1]).astype(float)

        if 'FECHA' in df.columns:
            df['FECHA_DT'] = df['FECHA'].apply(extraer_fecha_inteligente)
            df['MES'] = df['FECHA_DT'].dt.month
            df['ANIO'] = df['FECHA_DT'].dt.year
            
            # --- SOLUCIÓN AL ERROR DE LOCALE ---
            # Mapeo manual para evitar error en servidores Linux sin español instalado
            meses_es = {
                1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
                7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
            }
            df['MES_NOMBRE'] = df['MES'].map(meses_es).fillna('')

        return df
    except Exception as e:
        logger.error(f"Error construyendo DataFrame: {e}")
        return pd.DataFrame()

# --- 2. CONFIGURACIÓN DEL AGENTE DE ANÁLISIS ---

def crear_agente_pandas():
    df = get_dataframe_cliente()
    if df.empty: return None

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # Prompt diseñado para reducir errores de Pandas (Chain-of-Thought)
    prompt_prefix = """
    Eres un Analista de Datos experto trabajando con un DataFrame de Pandas llamado 'df'.
    
    ### ESTRUCTURA DE DATOS:
    - 'MONTO': Float. Usa esta columna para sumas y promedios. NUNCA uses 'COSTO' (es string).
    - 'MONEDA': String ('ARS', 'USD', 'EUR'). SIEMPRE agrupa por esta columna al sumar dinero.
    - 'FECHA_DT': Datetime. Úsala para filtrar por tiempo.
    - 'MES_NOMBRE': String. Contiene el nombre del mes en español (Enero, Febrero...).
    - 'INSTITUCIÓN', 'LUGAR', 'MOTIVO / EVENTO': Strings.
    
    ### REGLAS DE CODIFICACIÓN (CRÍTICO):
    1. **Filtrado de Texto:** Al filtrar strings, usa SIEMPRE `.str.contains('valor', case=False, na=False)`. Nunca uses `==` directo para texto libre.
    2. **Manejo de Errores:** Si te piden algo que no existe, verifica las columnas disponibles con `df.columns`.
    3. **Totales:** Si piden "gastos totales", devuelve la suma desglosada por MONEDA.
       Ejemplo de respuesta esperada: "Total en Pesos: $X, Total en Dólares: $Y".
    
    Si encuentras un error, intenta corregir tu propia consulta y prueba de nuevo.
    """

    return create_pandas_dataframe_agent(
        llm, 
        df, 
        verbose=True, 
        allow_dangerous_code=True,
        # Esta opción permite al sub-agente intentar corregir sus propios errores de Python
        # antes de devolver el control al agente principal.
        agent_executor_kwargs={"handle_parsing_errors": True},
        prefix=prompt_prefix,
        include_df_in_prompt=True
    )

# --- 3. HERRAMIENTA EXPUESTA (CON MANEJO DE ERRORES PARA EL GRAFO) ---

@tool
def analista_de_datos_cliente(consulta: str):
    """
    Herramienta AVANZADA de GESTIÓN INTERNA. 
    Especialista en: CÁLCULOS MATEMÁTICOS, sumas de costos, filtros complejos y reportes financieros.
    
    INPUT: Una descripción clara de qué calcular (ej: "Suma los gastos de viajes a Córdoba en Marzo").
    OUTPUT: El resultado del cálculo o un mensaje de error descriptivo.
    """
    try:
        agent = crear_agente_pandas()
        if agent is None: 
            return "Error Técnico: No se pudieron cargar los datos de la planilla. Verifica la conexión con Google Sheets."
        
        # Ejecución del agente de Pandas
        logger.info(f"📊 Analista procesando: {consulta}")
        response = agent.invoke({"input": consulta})
        
        output = response.get("output", "")
        
        # Validación de respuesta vacía o errónea
        if not output or "Agent stopped" in output:
            return "Error de Análisis: No pude llegar a una conclusión segura. Por favor reformula la pregunta simplificando los filtros."
            
        return output

    except Exception as e:
        # Capturamos el error y lo devolvemos como texto al Agente Principal.
        # Esto activa la "Autocorrección" en el grafo de LangGraph.
        error_msg = str(e)
        logger.error(f"❌ Error en Analista: {error_msg}")
        return f"FALLO EN EL CÁLCULO: Ocurrió el error '{error_msg}'. Por favor, intenta realizar la consulta nuevamente dividiéndola en pasos más simples."