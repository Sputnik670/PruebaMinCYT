import os
import json
import gspread
import logging
import io
import re
import unicodedata  # <--- NUEVO: Para manejar acentos
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from langchain.tools import tool
from cachetools import TTLCache, cached

logger = logging.getLogger(__name__)

# CONFIGURACIÓN
SHEET_MINISTERIO_ID = "1Sm2icTOvSbmGD7mdUtl2DfflUZqoHpBW" 
WORKSHEET_MINISTERIO_GID = 563858184
SHEET_CLIENTE_ID = "1HOiSJ-Hugkddv-kwGax6vhSV9tzthkiz" 
WORKSHEET_CLIENTE_GID = None 

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

# --- NUEVA FUNCIÓN DE LIMPIEZA SEGURA ---
def limpiar_nombre_columna(col_name):
    """
    Convierte 'Título' -> 'TITULO', 'Fecha inicio' -> 'FECHAINICIO'
    Elimina acentos y caracteres especiales pero mantiene las letras.
    """
    if not col_name: return ""
    s = str(col_name).upper()
    # Normalizar (eliminar acentos: Í -> I)
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    # Eliminar todo lo que no sea letra o número
    return re.sub(r'[^A-Z0-9]', '', s)

def leer_excel_drive(file_id, creds):
    try:
        service = build('drive', 'v3', credentials=creds)
        request = service.files().get_media(fileId=file_id)
        file_stream = io.BytesIO()
        downloader = MediaIoBaseDownload(file_stream, request)
        done = False
        while done is False: status, done = downloader.next_chunk()
        file_stream.seek(0)
        xls = pd.ExcelFile(file_stream)
        datos = []
        
        # Palabras clave ampliadas para detectar dónde empieza la tabla
        keywords_header = ['FECHA', 'DIA', 'INICIO', 'EVENTO', 'ACTIVIDAD', 'TITULO', 'LUGAR', 'DESTINO', 'NACINTL']

        for sheet_name in xls.sheet_names:
            # Leemos un trozo para encontrar el header
            df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=20)
            header_idx = -1
            
            for i, row in df_raw.iterrows():
                # Limpiamos la fila actual para ver si parece un header
                row_str = [limpiar_nombre_columna(x) for x in row.astype(str).tolist()]
                
                # Buscamos coincidencias (ahora TITULO coincidirá con TITULO)
                matches = sum(1 for k in keywords_header if any(k in s for s in row_str))
                
                if matches >= 2:
                    header_idx = i
                    logger.info(f"✅ Header detectado en fila {i} (Hoja: {sheet_name})")
                    break
            
            if header_idx == -1:
                logger.warning(f"⚠️ No se encontró header en {sheet_name}, saltando.")
                continue

            # Cargar datos reales
            df = pd.read_excel(xls, sheet_name=sheet_name, header=header_idx, dtype=str).fillna("")
            
            # Limpieza segura de columnas
            df.columns = [limpiar_nombre_columna(col) for col in df.columns]
            
            records = df.to_dict(orient='records')
            for r in records: r["_ORIGEN"] = sheet_name
            datos.extend(records)
            
        return datos
    except Exception as e:
        logger.error(f"Error Drive: {e}")
        return []

@cached(cache_agenda)
def obtener_datos_sheet_cached(sid, gid=None):
    creds = get_creds()
    if not creds: return []
    return leer_excel_drive(sid, creds)

def procesar_fila_cliente(fila):
    """Mapeo Gestión Interna"""
    def get_val(keys_list):
        for k in keys_list:
            # Búsqueda exacta
            if k in fila: return fila[k]
            # Búsqueda parcial (ej: FECHA en FECHADEINICIO)
            for col_real in fila.keys():
                if k in col_real: return fila[col_real]
        return ""

    item = {
        "FECHA_VIAJE": get_val(["FECHA", "INICIO", "SALIDA"]),
        "DESTINO": get_val(["LUGAR", "DESTINO", "CIUDAD"]),
        "FUNCIONARIO": get_val(["NOMBRE", "FUNCIONARIO", "PARTICIPANTE"]),
        "INSTITUCION": get_val(["INSTITUCION", "ORGANISMO"]),
        "MOTIVO_EVENTO": get_val(["MOTIVO", "EVENTO", "TITULO", "TEMA"]), # Agregado TITULO aquí
        "COSTO_TRASLADO": get_val(["COSTO", "PRECIO", "VALOR"]),
        "NUMERO_EXPEDIENTE": get_val(["EE", "EXPEDIENTE", "EXP"]) or "No especificado",
        "ESTADO_TRAMITE": get_val(["ESTADO"]),
    }
    
    # FILTRO ANTI-BASURA: Si no hay fecha ni evento, es una fila vacía o un título de mes
    if not item["FECHA_VIAJE"] and not item["MOTIVO_EVENTO"]:
        return None
        
    return item

def procesar_fila_ministerio(fila):
    """
    Intenta normalizar las columnas de la agenda pública.
    """
    def get_val(keys_list):
        # 1. Búsqueda exacta
        for k in keys_list:
            if k in fila: return fila[k]
        # 2. Búsqueda parcial
        for k in keys_list:
            for col_real in fila.keys():
                if k in col_real: return fila[col_real]
        return ""

    # Mapeo corregido para tu Excel específico
    raw_fecha = get_val(["FECHA", "INICIO", "DIA"])
    raw_evento = get_val(["TITULO", "EVENTO", "ACTIVIDAD", "TEMA"]) # 'TITULO' es clave aquí
    raw_lugar = get_val(["LUGAR", "UBICACION", "DESTINO"])

    # FILTRO ANTI-BASURA: Descartar filas que son solo nombres de meses (ej: "DICIEMBRE")
    # Si tiene menos de 2 campos llenos, probablemente no sirve
    llenos = sum(1 for x in [raw_fecha, raw_evento, raw_lugar] if len(str(x)) > 2)
    if llenos < 2:
        return None

    return {
        "FECHA": raw_fecha,
        "EVENTO": raw_evento,
        "LUGAR": raw_lugar
    }

def get_data_cliente_formatted():
    raw = obtener_datos_sheet_cached(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
    # Filtramos los Nones (filas basura)
    return [res for r in raw if (res := procesar_fila_cliente(r)) is not None]

def get_data_ministerio_formatted():
    raw = obtener_datos_sheet_cached(SHEET_MINISTERIO_ID, WORKSHEET_MINISTERIO_GID)
    # Filtramos los Nones (filas basura)
    return [res for r in raw if (res := procesar_fila_ministerio(r)) is not None]

def obtener_datos_raw():
    return get_data_cliente_formatted() + get_data_ministerio_formatted()

# TOOLS
@tool
def consultar_calendario_cliente(q: str): 
    """Consulta agenda interna. JSON crudo."""
    return json.dumps(get_data_cliente_formatted(), ensure_ascii=False, default=str)

@tool
def consultar_calendario_ministerio(q: str): 
    """Consulta agenda pública."""
    return json.dumps(get_data_ministerio_formatted(), ensure_ascii=False, default=str)