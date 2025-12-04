import os
import json
import gspread
import logging
import io
import re
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
        
        for sheet_name in xls.sheet_names:
            # Detectar header real (Buscamos 'FECHA' y 'LUGAR')
            df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=15)
            header_idx = 0
            for i, row in df_raw.iterrows():
                row_str = row.astype(str).str.upper().str.replace('\n', '').tolist()
                if any('FECHA' in s for s in row_str) and any('LUGAR' in s for s in row_str):
                    header_idx = i
                    break
            
            # Cargar datos con header correcto
            df = pd.read_excel(xls, sheet_name=sheet_name, header=header_idx, dtype=str).fillna("")
            
            # Limpieza agresiva de nombres de columnas
            # "COSTO DEL \n TRASLADO" -> "COSTODELTRASLADO"
            df.columns = [re.sub(r'[^A-Z0-9]', '', str(col).upper()) for col in df.columns]
            
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
    """
    Mapeo usando claves 100% limpias (solo letras y números).
    """
    # fila ya viene con claves limpias desde leer_excel_drive (ej: 'COSTODELTRASLADO')
    # pero por seguridad volvemos a limpiar al buscar
    
    def get_val(keys_list):
        for k in keys_list:
            if k in fila: return fila[k]
        return ""

    return {
        "FECHA_VIAJE": get_val(["FECHA", "FECHADESALIDA"]),
        "DESTINO": get_val(["LUGAR", "DESTINO", "CIUDAD"]),
        "FUNCIONARIO": get_val(["NOMBRE", "FUNCIONARIO", "APELLIDOYNOMBRE"]),
        "INSTITUCION": get_val(["INSTITUCION", "INSTITUCIÓN", "ORGANISMO"]),
        "MOTIVO_EVENTO": get_val(["MOTIVO", "EVENTO", "MOTIVOEVENTO"]),
        
        # COSTO: Clave limpia es COSTODELTRASLADO
        "COSTO_TRASLADO": get_val(["COSTODELTRASLADO", "COSTO", "PRECIO", "VALOR"]),
        
        # EXPEDIENTE: Clave limpia es EE. Agregamos variantes por si acaso.
        "NUMERO_EXPEDIENTE": get_val(["EE", "EXPEDIENTE", "EXP", "NROEXPEDIENTE", "NROEE"]) or "No especificado",
        
        "ESTADO_TRAMITE": get_val(["ESTADO", "ESTADODELTRAMITE"]),
        "AUTORIZACION": get_val(["AUTORIZACION", "AUTORIZACIÓN"]),
        "RENDICION": get_val(["RENDICION", "RENDICIÓN"])
    }

def get_data_cliente_formatted():
    raw = obtener_datos_sheet_cached(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
    return [procesar_fila_cliente(r) for r in raw]

def get_data_ministerio_formatted():
    raw = obtener_datos_sheet_cached(SHEET_MINISTERIO_ID, WORKSHEET_MINISTERIO_GID)
    return [{"FECHA": str(r.get("FECHA","")), "EVENTO": str(r.get("EVENTO",""))} for r in raw] # Ajuste simple

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