import os
import io
import re
import logging
import unicodedata
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# IDS ORIGINALES
SHEET_MINISTERIO_ID = "1Sm2icTOvSbmGD7mdUtl2DfflUZqoHpBW" 
SHEET_CLIENTE_ID = "1HOiSJ-Hugkddv-kwGax6vhSV9tzthkiz" 

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
    }
    return service_account.Credentials.from_service_account_info(
        creds_dict, 
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )

def limpiar_nombre_columna(col_name):
    if not col_name: return ""
    s = str(col_name).upper()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Z0-9]', '', s)

def formatear_fecha_sin_hora(valor):
    if not valor: return ""
    texto = str(valor)
    if " 00:00:00" in texto:
        return texto.replace(" 00:00:00", "").strip()
    return texto

def leer_excel_drive(file_id):
    creds = get_creds()
    if not creds: return []
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
        # Palabras clave ampliadas para detectar ambos tipos de headers
        keywords_header = [
            'FECHA', 'DIA', 'INICIO', 'EVENTO', 'ACTIVIDAD', 'TITULO', 
            'LUGAR', 'DESTINO', 'COSTO', 'PRECIO', 'ORGANIZADOR', 'PARTICIPANTE'
        ]

        for sheet_name in xls.sheet_names:
            df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=20)
            header_idx = -1
            for i, row in df_raw.iterrows():
                row_str = [limpiar_nombre_columna(x) for x in row.astype(str).tolist()]
                matches = sum(1 for k in keywords_header if any(k in s for s in row_str))
                if matches >= 2:
                    header_idx = i
                    break
            
            if header_idx == -1: continue

            df = pd.read_excel(xls, sheet_name=sheet_name, header=header_idx, dtype=str).fillna("")
            df.columns = [limpiar_nombre_columna(col) for col in df.columns]
            datos.extend(df.to_dict(orient='records'))
            
        return datos
    except Exception as e:
        logger.error(f"Error Drive: {e}")
        return []

# --- PROCESADORES ESPECÍFICOS ---

def procesar_fila_cliente(fila):
    def get_val(keys_list):
        for k in keys_list:
            if k in fila: return fila[k]
            for col_real in fila.keys():
                if k in col_real: return fila[col_real]
        return ""

    raw_fecha = formatear_fecha_sin_hora(get_val(["FECHA", "INICIO", "SALIDA"]))
    if not raw_fecha: 
        if not get_val(["MOTIVO", "EVENTO", "TITULO"]): return None

    return {
        "FECHA_VIAJE": raw_fecha,
        "DESTINO": get_val(["LUGAR", "DESTINO", "CIUDAD"]),
        "FUNCIONARIO": get_val(["NOMBRE", "FUNCIONARIO", "PARTICIPANTE"]),
        "MOTIVO_EVENTO": get_val(["MOTIVO", "EVENTO", "TITULO", "TEMA"]), 
        "COSTO_TRASLADO": get_val(["COSTO", "PRECIO", "VALOR"]),
        "NUMERO_EXPEDIENTE": get_val(["EE", "EXPEDIENTE", "EXP"]) or "No especificado",
        "ESTADO_TRAMITE": get_val(["ESTADO"]),
        "AMBITO": "Gestión Interna"
    }

def procesar_fila_ministerio(fila):
    def get_val(keys_list):
        for k in keys_list:
            if k in fila: return fila[k]
            for col_real in fila.keys():
                if k in col_real: return fila[col_real]
        return ""

    raw_fecha = formatear_fecha_sin_hora(get_val(["FECHA", "INICIO", "DIA", "DESDE"]))
    raw_evento = get_val(["TITULO", "EVENTO", "ACTIVIDAD", "TEMA", "NOMBRE"])
    
    if len(raw_fecha) < 2 or len(raw_evento) < 2: return None

    raw_ambito = get_val(["NACINTL", "AMBITO", "TIPO"])
    if "NAC" in str(raw_ambito).upper(): raw_ambito = "Nacional"
    elif "INT" in str(raw_ambito).upper(): raw_ambito = "Internacional"

    return {
        "FECHA": raw_fecha,
        "EVENTO": raw_evento,
        "LUGAR": get_val(["LUGAR", "UBICACION", "DESTINO", "PAIS", "CIUDAD"]),
        "ORGANIZADOR": get_val(["ORGANIZADOR", "INVITA", "ORGANIZA"]),
        "PARTICIPANTE": get_val(["PARTICIPANTE", "FUNCIONARIO", "QUIEN"]),
        "AMBITO": raw_ambito
    }

def get_data_cliente_legacy():
    print(f"📥 Leyendo Gestión Interna ({SHEET_CLIENTE_ID})...")
    raw = leer_excel_drive(SHEET_CLIENTE_ID)
    return [res for r in raw if (res := procesar_fila_cliente(r)) is not None]

def get_data_ministerio_legacy():
    print(f"📥 Leyendo Agenda Oficial ({SHEET_MINISTERIO_ID})...")
    raw = leer_excel_drive(SHEET_MINISTERIO_ID)
    return [res for r in raw if (res := procesar_fila_ministerio(r)) is not None]