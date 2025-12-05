import os
import json
import logging
import io
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from langchain.tools import tool
from cachetools import TTLCache, cached

logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN ESTRICTA DE ARCHIVOS (Adaptador para el Cliente) ---
CONFIG_ARCHIVOS = {
    "MINISTERIO": {
        "ID": "1Sm2icTOvSbmGD7mdUtl2DfflUZqoHpBW", # CalendariosInternacionales
        "GID": 563858184, 
        "HEADER_ROW": 4,  # 🔴 IMPORTANTE: Verifica esto. Si en el Excel la fila es la 5, aquí pon 4.
        "MAPEO_COLUMNAS": {
            # Nombre EXACTO en tu Excel -> Nombre INTERNO para el Agente
            "Fecha inicio": "FECHA",
            "Título": "EVENTO",
            "Lugar": "LUGAR",
            "Nac/Intl": "AMBITO",
            "Organizador": "ORGANIZADOR",
            "Participante": "PARTICIPANTE",
            "Observaciones": "OBSERVACIONES"
            # Ignoramos checkbox, Fecha fin y ¿Pagan? si no son críticas para el agente
        }
    },
    "CLIENTE": {
        "ID": "1HOiSJ-Hugkddv-kwGax6vhSV9tzthkiz", # MisionesOficialesSICyT
        "GID": None,
        "HEADER_ROW": 0, # 🔴 IMPORTANTE: Verifica esto. Si los títulos están en la primera fila, deja 0.
        "MAPEO_COLUMNAS": {
            # Nombre EXACTO en tu Excel -> Nombre INTERNO para el Agente
            "FECHA": "FECHA",
            "MOTIVO": "EVENTO",
            "LUGAR": "LUGAR",
            "COSTO DEL TRASLADO": "COSTO",
            "EE": "EXPEDIENTE",
            "NOMBRE": "FUNCIONARIO",
            "INSTITUCIÓN": "INSTITUCION",
            "ESTADO": "ESTADO"
            # Las columnas de fechas de autorización/rendición las podemos agregar si el agente las necesita
        }
    }
}

cache_agenda = TTLCache(maxsize=5, ttl=600)

def get_creds():
    private_key = os.getenv("GOOGLE_PRIVATE_KEY")
    client_email = os.getenv("GOOGLE_CLIENT_EMAIL")
    if not private_key or not client_email: return None
    creds_dict = {
        "type": "service_account",
        "project_id": "dashboard-impacto-478615",
        "private_key_id": "indefinido",
        "private_key": private_key.replace("\\n", "\n"),
        "client_email": client_email,
        "client_id": "116197238257458301101",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email}"
    }
    return service_account.Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])

# --- FUNCIONES DE LIMPIEZA ---

def formatear_fecha_sin_hora(valor):
    """Limpia timestamps de pandas (ej: 2025-01-01 00:00:00 -> 2025-01-01)"""
    if not valor: return ""
    texto = str(valor)
    if " 00:00:00" in texto:
        return texto.replace(" 00:00:00", "").strip()
    return texto

def leer_excel_estricto(tipo_archivo):
    """
    Descarga y lee el Excel usando la configuración estricta definida arriba.
    """
    creds = get_creds()
    if not creds: return []
    
    config = CONFIG_ARCHIVOS.get(tipo_archivo)
    if not config: return []

    try:
        service = build('drive', 'v3', credentials=creds)
        request = service.files().get_media(fileId=config["ID"])
        file_stream = io.BytesIO()
        downloader = MediaIoBaseDownload(file_stream, request)
        done = False
        while done is False: status, done = downloader.next_chunk()
        file_stream.seek(0)

        # Leemos usando la fila de encabezado EXACTA
        df = pd.read_excel(
            file_stream, 
            sheet_name=0, 
            header=config["HEADER_ROW"], 
            dtype=str
        )
        
        # Validar y Seleccionar Columnas
        mapeo = config["MAPEO_COLUMNAS"]
        # Filtramos solo las que existen para evitar crash si el cliente borró una columna menor
        columnas_validas = [col for col in mapeo.keys() if col in df.columns]
        
        # Renombrar a nuestro estándar interno (FECHA, EVENTO, etc.)
        df_final = df[columnas_validas].rename(columns=mapeo)
        
        # Limpieza básica
        df_final = df_final.dropna(how='all')
        df_final = df_final.fillna("")
        
        if "FECHA" in df_final.columns:
            df_final["FECHA"] = df_final["FECHA"].apply(formatear_fecha_sin_hora)

        # Etiqueta vital para que el Agente sepa si es dato Público o Privado
        df_final["ORIGEN_DATO"] = tipo_archivo 
        
        logger.info(f"✅ {tipo_archivo} procesado correctamente: {len(df_final)} filas.")
        return df_final.to_dict(orient="records")

    except Exception as e:
        logger.error(f"❌ Error leyendo {tipo_archivo}: {e}", exc_info=True)
        return []

# --- GETTERS CACHEADOS ---

@cached(cache_agenda)
def get_data_cliente_formatted():
    return leer_excel_estricto("CLIENTE")

@cached(cache_agenda)
def get_data_ministerio_formatted():
    return leer_excel_estricto("MINISTERIO")

def obtener_datos_raw():
    return get_data_cliente_formatted() + get_data_ministerio_formatted()

# --- TOOLS PARA EL AGENTE ---

@tool
def consultar_calendario_cliente(q: str): 
    """
    Consulta la agenda interna de gestión (Misiones Oficiales).
    Devuelve JSON con campos: FECHA, EVENTO, LUGAR, COSTO, EXPEDIENTE, ESTADO.
    """
    return json.dumps(get_data_cliente_formatted(), ensure_ascii=False, default=str)

@tool
def consultar_calendario_ministerio(q: str): 
    """
    Consulta la agenda pública oficial (Calendarios Internacionales).
    Devuelve JSON con campos: FECHA, EVENTO, LUGAR, AMBITO, ORGANIZADOR.
    """
    return json.dumps(get_data_ministerio_formatted(), ensure_ascii=False, default=str)