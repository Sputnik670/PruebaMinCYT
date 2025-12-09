import os
import logging
import pandas as pd
import time
from dotenv import load_dotenv
from supabase import create_client
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import tool

load_dotenv()
logger = logging.getLogger(__name__)

SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# --- CACHÉ EN MEMORIA (TTL) ---
# Evita golpear la BD en cada interacción del chat
_CACHE_DF = None
_LAST_UPDATE = 0
CACHE_TTL = 300  # 5 minutos

def get_df_optimizado():
    global _CACHE_DF, _LAST_UPDATE
    try:
        now = time.time()
        # Si el caché es válido, úsalo
        if _CACHE_DF is not None and (now - _LAST_UPDATE < CACHE_TTL):
            return _CACHE_DF

        if not SUPA_URL or not SUPA_KEY:
            return pd.DataFrame()

        supabase = create_client(SUPA_URL, SUPA_KEY)
        
        # Consultamos aumentando el límite (Supabase trae 1000 por defecto)
        # Traemos campos clave insertados por tu sync_sheets.py
        response = supabase.table("agenda_unificada")\
            .select("fecha, titulo, funcionario, lugar, costo, moneda, ambito, organizador, origen_dato")\
            .limit(10000)\
            .execute()
        
        datos = response.data
        if not datos: return pd.DataFrame()
            
        df = pd.DataFrame(datos)
        
        # Normalización para el LLM
        if 'fecha' in df.columns:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
        if 'costo' in df.columns:
            df['costo'] = pd.to_numeric(df['costo'], errors='coerce').fillna(0)
            
        df = df.fillna('')
        
        # Columnas auxiliares para búsqueda insensible a mayúsculas
        df['lugar_norm'] = df['lugar'].astype(str).str.lower()
        df['funcionario_norm'] = df['funcionario'].astype(str).str.lower()
        
        _CACHE_DF = df
        _LAST_UPDATE = now
        logger.info(f"✅ Datos recargados: {len(df)} registros.")
        return df
        
    except Exception as e:
        logger.error(f"Error leyendo Supabase: {e}")
        return _CACHE_DF if _CACHE_DF is not None else pd.DataFrame()

@tool
def analista_de_datos_cliente(consulta: str):
    """
    [DEPARTAMENTO DE DATOS]
    Úsala SIEMPRE que pregunten por: agenda, viajes, gastos, funcionarios, expedientes o lugares.
    """
    try:
        df = get_df_optimizado()
        if df.empty: return "Error: Base de datos vacía."

        # --- DICCIONARIO DE DATOS (Anti-Alucinación) ---
        # Le explicamos al LLM qué significa cada columna exactamente
        data_dictionary = """
        DICCIONARIO DE COLUMNAS (ÚSALO ESTRICTAMENTE):
        - 'costo': Es el valor numérico del gasto. Si es 0, es que no hay dato.
        - 'moneda': Puede ser 'ARS', 'USD', 'EUR'. ¡NO SUMES MONEDAS DISTINTAS!
        - 'ambito': 'Oficial' (Agenda Pública), 'Gestión' (Interna), 'Nacional', 'Internacional'.
        - 'lugar': Ciudad o País. Para buscar aquí usa: df[df['lugar_norm'].str.contains('termino', case=False)]
        - 'funcionario': Nombre de la persona. Búsqueda parcial: df[df['funcionario_norm'].str.contains('nombre', case=False)]
        - 'num_expediente': Código administrativo (ej: EX-2024-...).
        - 'origen_dato': Indica de qué Excel vino el dato.
        """

        llm = ChatGoogleGenerativeAI(model="models/gemini-2.0-flash-001", temperature=0)
        
        prefix = f"""
        Eres un Analista de Datos SQL/Pandas riguroso. 
        Tienes un DataFrame `df` con {len(df)} registros.
        
        {data_dictionary}

        ### REGLAS DE ORO (Si las rompes, fallarás):
        1. **Búsqueda Flexible:** Si buscan "Córdoba", busca en `lugar_norm` usando `.str.contains('cordoba', case=False)`. Nunca busques igualdad exacta (==).
        2. **Case Insensitive:** Convierte siempre la búsqueda del usuario a minúsculas para comparar con `_norm`.
        3. **Sumar Costos:** SIEMPRE agrupa por moneda: `df.groupby('moneda')['costo'].sum()`.
        4. **Fechas:** Usa `pd.to_datetime`. Hoy es {pd.Timestamp.now().strftime('%Y-%m-%d')}.
        5. **Honestidad:** Si el DataFrame vacío tras filtrar, di "No encontré registros que coincidan", NO INVENTES DATOS.

        Pregunta del usuario: {consulta}
        """

        agent = create_pandas_dataframe_agent(
            llm, df, verbose=True, allow_dangerous_code=True,
            prefix=prefix, include_df_in_prompt=False, number_of_head_rows=5
        )
        
        return agent.invoke({"input": consulta})["output"]

    except Exception as e:
        logger.error(f"Error analista: {e}")
        return "Hubo un error técnico consultando los datos."