import os
import logging
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool

load_dotenv()
logger = logging.getLogger(__name__)

# Credenciales
SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def get_df_optimizado():
    """
    Obtiene datos FRESCOS directamente de la tabla 'agenda_unificada' en Supabase.
    """
    try:
        if not SUPA_URL or not SUPA_KEY:
            logger.error("❌ Faltan credenciales de Supabase en analysis.py")
            return pd.DataFrame()

        supabase = create_client(SUPA_URL, SUPA_KEY)
        
        # Consultamos la tabla maestra (Gestión + Oficial)
        response = supabase.table("agenda_unificada").select("*").execute()
        datos = response.data
        
        if not datos:
            logger.warning("⚠️ La tabla 'agenda_unificada' está vacía o no se pudo leer.")
            return pd.DataFrame()
            
        df = pd.DataFrame(datos)
        
        # --- LIMPIEZA Y NORMALIZACIÓN ---
        if 'fecha' in df.columns:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        
        if 'costo' in df.columns:
            df['costo'] = pd.to_numeric(df['costo'], errors='coerce').fillna(0)
            
        # Rellenar nulos para evitar errores en el LLM
        df = df.fillna({
            'titulo': 'Sin título',
            'lugar': 'Desconocido',
            'funcionario': 'No asignado',
            'moneda': 'Sin especificar',
            'ambito': 'Desconocido',
            'organizador': ''
        })
        
        # Columnas auxiliares para búsqueda insensible a mayúsculas (Normalización)
        df['lugar_norm'] = df['lugar'].astype(str).str.lower()
        df['titulo_norm'] = df['titulo'].astype(str).str.lower()
        df['funcionario_norm'] = df['funcionario'].astype(str).str.lower()
        
        return df
        
    except Exception as e:
        logger.error(f"❌ Error crítico leyendo Supabase: {e}")
        return pd.DataFrame()

@tool
def analista_de_datos_cliente(consulta: str):
    """
    [DEPARTAMENTO DE DATOS]
    Motor de análisis sobre la Agenda Unificada (Gestión Interna + Agenda Oficial).
    Usa esta herramienta para responder preguntas sobre:
    - Viajes, Costos, Presupuestos.
    - Eventos de la Agenda Oficial.
    - Funcionarios, Lugares y Fechas.
    """
    try:
        df = get_df_optimizado()
        
        if df.empty: 
            return "Error: No se pudieron cargar datos. Verifica que la sincronización se haya ejecutado correctamente."

        # --- CONTEXTO REAL (Grounding) ---
        # Le damos al LLM una muestra de lo que hay en la BD para que se ubique
        lista_lugares = df['lugar'].unique().tolist() if 'lugar' in df.columns else []
        lista_monedas = df['moneda'].unique().tolist() if 'moneda' in df.columns else []
        lista_ambitos = df['ambito'].unique().tolist() if 'ambito' in df.columns else []
        
        llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash-001", temperature=0)
        
        prefix = f"""
        Eres un Analista de Datos experto. Trabajas con un DataFrame `df` que contiene la AGENDA UNIFICADA del organismo.
        
        ### DATOS DISPONIBLES EN TU BASE DE DATOS:
        - Ámbitos detectados: {lista_ambitos} (Ej: 'Oficial', 'Gestión Interna')
        - Monedas: {lista_monedas}
        - Lugares (muestra): {str(lista_lugares[:10])}...
        - Columnas útiles: fecha, titulo, funcionario, lugar, costo, moneda, ambito, organizador.
        
        ### INSTRUCCIONES DE BÚSQUEDA (PYTHON PANDAS):
        1. **Agenda Oficial:** Filtra usando `df[df['ambito'].str.contains('Oficial', case=False)]` o busca 'Agenda Oficial' en `origen_dato`.
        2. **Búsqueda de Texto:** Usa siempre `.str.contains('texto', case=False, na=False)` en columnas `_norm`.
        3. **Costos:** Agrupa SIEMPRE por moneda (`groupby('moneda')`). ¡No sumes peras con manzanas!
        4. **Fechas:** Si piden 'próximos eventos', filtra `df['fecha'] >= pd.Timestamp.now()`.
        
        Consulta del usuario: {consulta}
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
        
        return agent.invoke({"input": consulta})["output"]

    except Exception as e:
        logger.error(f"Error en analista: {e}", exc_info=True)
        return "Tuve un problema técnico analizando los datos."