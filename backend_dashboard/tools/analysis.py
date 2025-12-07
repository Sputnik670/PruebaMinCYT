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
    Obtiene datos de SQL y genera un DataFrame unificado y optimizado para IA.
    """
    data_cliente = get_data_cliente_formatted() or []
    data_ministerio = get_data_ministerio_formatted() or []
    
    todos_los_datos = data_cliente + data_ministerio
    
    if not todos_los_datos: 
        return pd.DataFrame()
    
    df = pd.DataFrame(todos_los_datos)
    
    # --- 1. LIMPIEZA DE DATOS (Robusta) ---
    if 'fecha' in df.columns:
        df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    if 'fecha_fin' in df.columns:
        df['fecha_fin'] = pd.to_datetime(df['fecha_fin'], errors='coerce')
    if 'costo' in df.columns:
        df['costo'] = pd.to_numeric(df['costo'], errors='coerce').fillna(0)
        
    # Rellenar nulos (SIN FORZAR MONEDA A ARS)
    # Eliminamos 'moneda': 'ARS' de aquí para no sobrescribir datos valiosos
    df = df.fillna({
        'titulo': 'Sin título',
        'lugar': 'Desconocido',
        'funcionario': 'No asignado',
        'origen_dato': 'Desconocido'
    })
    
    # Manejo inteligente de moneda: Si no existe o es nula, poner "Sin especificar"
    if 'moneda' not in df.columns:
        df['moneda'] = 'Sin especificar'
    else:
        # Convertimos a string y rellenamos nulos para asegurar que el GroupBy funcione
        df['moneda'] = df['moneda'].fillna('Sin especificar').astype(str)

    # --- 2. COLUMNAS NORMALIZADAS (Para búsqueda fácil) ---
    # Creamos copias en minúsculas. Ayuda a encontrar "Washington" si el usuario escribe "washington"
    df['lugar_norm'] = df['lugar'].astype(str).str.lower()
    df['titulo_norm'] = df['titulo'].astype(str).str.lower()
    df['funcionario_norm'] = df['funcionario'].astype(str).str.lower()
    
    return df

@tool
def analista_de_datos_cliente(consulta: str):
    """
    [DEPARTAMENTO DE DATOS]
    Motor de análisis forense sobre SQL. 
    Usa esta herramienta para CUALQUIER pregunta sobre costos, fechas, viajes, agenda o funcionarios.
    """
    try:
        df = get_df_optimizado()
        
        # --- 🔍 LOG DE DIAGNÓSTICO EN TERMINAL ---
        print(f"\n📊 [DEBUG ANALISTA] DataFrame cargado: {len(df)} filas.")
        if not df.empty:
            # Mostramos las monedas detectadas para confirmar que llegan bien (ej: ['USD', 'EUR', 'ARS'])
            monedas_unicas = df['moneda'].unique().tolist() if 'moneda' in df.columns else []
            print(f"   💰 [DEBUG] Monedas detectadas en BD: {monedas_unicas}")
        else:
            print("   ⚠️ ATENCIÓN: El DataFrame está vacío.")
        # ------------------------------------------

        if df.empty: 
            return "Error: La base de datos está vacía. No hay registros para analizar."

        # --- 3. GROUNDING (Inyección de Contexto Real) ---
        lista_lugares = df['lugar'].unique().tolist() if 'lugar' in df.columns else []
        lista_monedas = df['moneda'].unique().tolist() if 'moneda' in df.columns else []
        
        # Le damos una "memoria" de qué valores existen realmente
        preview_lugares = str(lista_lugares[:50]) 

        llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash-001", temperature=0)
        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        
        # --- 4. PROMPT DE SEGURIDAD MULTIMONEDA ---
        prefix = f"""
        Eres un Analista de Datos experto en Pandas (Python).
        HOY ES: {fecha_actual}.

        ### ⚠️ INSTRUCCIONES DE EJECUCIÓN (CRÍTICO):
        1. **LA VARIABLE `df` YA EXISTE EN MEMORIA.** - **PROHIBIDO** hacer `df = pd.read_csv(...)`. 
           - **PROHIBIDO** crear datos de ejemplo (`data = ...`).
           - Debes trabajar DIRECTAMENTE sobre la variable `df` que se te ha pasado.

        2. **MEMORIA DE DATOS REALES (Úsala para filtrar):**
           - Lugares existentes: {preview_lugares}...
           - **MONEDAS DISPONIBLES:** {lista_monedas} (¡Importante para cálculos!)

        3. **SINTAXIS DE BÚSQUEDA SEGURA:**
           - Usa SIEMPRE `.str.contains('texto', case=False, na=False)` sobre las columnas `_norm`.
           - Ejemplo: `df[df['lugar_norm'].str.contains('washington', case=False, na=False)]`

        4. **CÁLCULO DE COSTOS (IMPORTANTE):**
           - **NUNCA** sumes costos de monedas diferentes (ej: no sumes USD con ARS).
           - Haz SIEMPRE: `df.groupby('moneda')['costo'].sum()`.
           - Si te piden un total, reporta el desglose (Ej: "1000 USD y 50000 ARS").

        5. **VERIFICACIÓN DE VACÍO:**
           - Si el resultado de tu filtro es vacío, responde: "No se encontraron registros en la base de datos."

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
        
        respuesta = str(resultado["output"])
        if "Agent stopped" in respuesta:
            return "El análisis se detuvo. Por favor intenta ser más específico con tu pregunta."
            
        return respuesta

    except Exception as e:
        logger.error(f"Error crítico en analista: {e}", exc_info=True)
        return "Tuve un error técnico leyendo los datos. Intenta nuevamente."