import os
import json
import gspread
import logging
import io
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from langchain.tools import tool
from cachetools import TTLCache, cached

# Configurar Logger
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DE TABLAS ---
SHEET_MINISTERIO_ID = "1Sm2icTOvSbmGD7mdUtl2DfflUZqoHpBW" 
WORKSHEET_MINISTERIO_GID = 563858184

SHEET_CLIENTE_ID = "1HOiSJ-Hugkddv-kwGax6vhSV9tzthkiz" 
WORKSHEET_CLIENTE_GID = None 

# --- CACHÉ ---
cache_agenda = TTLCache(maxsize=5, ttl=600)

def get_creds():
    """Obtiene credenciales para Gspread y Drive API"""
    private_key = os.getenv("GOOGLE_PRIVATE_KEY")
    client_email = os.getenv("GOOGLE_CLIENT_EMAIL")
    
    if not private_key or not client_email: 
        return None

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
    return service_account.Credentials.from_service_account_info(creds_dict, scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ])

def leer_excel_drive(file_id, creds):
    """Fallback: Descarga .xlsx desde Drive y lo lee con Pandas"""
    try:
        logger.info(f"📥 Intentando descargar archivo Excel (ID: {file_id})...")
        service = build('drive', 'v3', credentials=creds)
        request = service.files().get_media(fileId=file_id)
        
        file_stream = io.BytesIO()
        downloader = MediaIoBaseDownload(file_stream, request)
        
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            
        file_stream.seek(0)
        
        # Leemos todas las pestañas
        xls = pd.ExcelFile(file_stream)
        datos_totales = []
        
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name, dtype=str) # Todo como string para evitar errores
            df = df.fillna("") # Reemplazar NaN por vacíos
            
            # Convertir a lista de diccionarios
            records = df.to_dict(orient='records')
            for r in records:
                r["_ORIGEN"] = sheet_name # Marca de origen
                datos_totales.append(r)
                
        logger.info(f"✅ Excel leído correctamente: {len(datos_totales)} filas.")
        return datos_totales

    except Exception as e:
        logger.error(f"❌ Error leyendo Excel desde Drive: {e}")
        return []

def obtener_datos_sheet(spreadsheet_id: str, worksheet_gid: int = None):
    """
    Intenta leer como Google Sheet nativo. Si falla, prueba como Excel.
    """
    creds = get_creds()
    if not creds: return []

    try:
        # 1. Intento Google Sheet Nativo (Rápido)
        client = gspread.authorize(creds)
        sh = client.open_by_key(spreadsheet_id)
        
        hojas_a_leer = []
        if worksheet_gid is not None:
            try:
                w = sh.get_worksheet_by_id(worksheet_gid)
                if w: hojas_a_leer.append(w)
            except: pass
        else:
            hojas_a_leer = sh.worksheets()
            
        datos_consolidados = []
        for worksheet in hojas_a_leer:
            data = worksheet.get_all_records() # gspread lo hace automático
            # Agregamos origen manual
            for d in data: d["_ORIGEN"] = worksheet.title
            datos_consolidados.extend(data)
            
        return datos_consolidados

    except Exception as e:
        # 2. Si falla (ej: error 400 por ser Excel), usamos el Plan B
        if "400" in str(e) or "not supported" in str(e):
            logger.warning(f"⚠️ Detectado archivo Excel no nativo. Cambiando a modo descarga Drive...")
            return leer_excel_drive(spreadsheet_id, creds)
        else:
            logger.error(f"❌ Error general en lectura: {e}")
            return []

# --- WRAPPER CON CACHÉ ---
@cached(cache_agenda)
def obtener_datos_sheet_cached(spreadsheet_id: str, worksheet_gid: int = None):
    return obtener_datos_sheet(spreadsheet_id, worksheet_gid)

# --- PROCESAMIENTO (Mantenemos tu lógica inteligente) ---

def buscar_valor_inteligente(fila_map, keywords_primarias, keywords_secundarias=None):
    for key, value in fila_map.items():
        if any(p == key for p in keywords_primarias): return value
        if any(f" {p} " in f" {key} " for p in keywords_primarias): return value

    match_secundario = None
    all_keywords = keywords_primarias + (keywords_secundarias or [])
    for key, value in fila_map.items():
        if any(p in key for p in all_keywords):
            if not match_secundario and value: match_secundario = value
    return match_secundario or ""

def procesar_fila_cliente(fila):
    f_map = {str(k).lower().strip(): v for k, v in fila.items()}
    
    return {
        "FECHA": buscar_valor_inteligente(f_map, ["fecha de salida", "fecha salida", "fecha ida", "salida"], ["fecha", "día"]),
        "MOTIVO / EVENTO": buscar_valor_inteligente(f_map, ["motivo", "evento", "descripción"], ["título"]) or "Sin título",
        "LUGAR": buscar_valor_inteligente(f_map, ["lugar", "destino", "ciudad"], ["ubicación"]),
        "INSTITUCIÓN": buscar_valor_inteligente(f_map, ["institución", "organismo", "empresa"], ["pasajero"]),
        "COSTO": buscar_valor_inteligente(f_map, ["costo", "precio", "monto", "valor"], ["presupuesto"]) or "0", 
        "ESTADO": buscar_valor_inteligente(f_map, ["estado", "status"], []),
        "RENDICIÓN": buscar_valor_inteligente(f_map, ["rendición", "expediente"], ["ee"]),
        "F. REGRESO": buscar_valor_inteligente(f_map, ["fecha de regreso", "regreso"], ["fin"]),
        "HOJA_ORIGEN": f_map.get("_origen", "")
    }

def procesar_fila_ministerio(fila):
    f_map = {str(k).lower().strip(): v for k, v in fila.items()}
    return {
        "FECHA": buscar_valor_inteligente(f_map, ["fecha", "día"], ["cuándo"]),
        "HORA": buscar_valor_inteligente(f_map, ["hora", "horario"], ["hs"]),
        "EVENTO": buscar_valor_inteligente(f_map, ["evento", "título", "actividad"], ["qué"]),
        "LUGAR": buscar_valor_inteligente(f_map, ["lugar", "ubicación"], ["dónde"])
    }

# --- EXPORTACIONES ---

def get_data_cliente_formatted():
    raw = obtener_datos_sheet_cached(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
    return [procesar_fila_cliente(r) for r in raw]

def get_data_ministerio_formatted():
    raw = obtener_datos_sheet_cached(SHEET_MINISTERIO_ID, WORKSHEET_MINISTERIO_GID)
    return [procesar_fila_ministerio(r) for r in raw]

def obtener_datos_raw():
    return get_data_cliente_formatted() + get_data_ministerio_formatted()

# --- TOOLS ---

@tool
def analizar_estructura_tablas(consulta: str):
    """Diagnóstico de columnas para ver qué detecta el sistema."""
    try:
        raw_data = obtener_datos_sheet_cached(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
        if not raw_data: return "Error: No data."
        return f"Total: {len(raw_data)}\nCols: {list(raw_data[0].keys())}\nEj: {json.dumps(raw_data[0], default=str)}"
    except Exception as e: return str(e)

@tool
def consultar_calendario_ministerio(consulta: str):
    """
    Consulta la Agenda Pública Oficial del Ministro. 
    Devuelve eventos protocolares, actos y reuniones oficiales.
    """
    return json.dumps(get_data_ministerio_formatted(), ensure_ascii=False, default=str)

@tool
def consultar_calendario_cliente(consulta: str):
    """
    Consulta la Agenda de Gestión Interna (Logística, Viajes, Misiones).
    Útil para ver el listado de movimientos internos.
    """
    return json.dumps(get_data_cliente_formatted(), ensure_ascii=False, default=str)