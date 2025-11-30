import os
import json
import gspread
import logging
from google.oauth2 import service_account
from langchain.tools import tool

# Configurar Logger específico para este módulo
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DE TABLAS (GOOGLE SHEETS) ---
SHEET_MINISTERIO_ID = "1lkViCdCeq7F4yEHVdbjfrV-G7KvKP6TZfxsOc-Ov4xI"
WORKSHEET_MINISTERIO_GID = 563858184

SHEET_CLIENTE_ID = "1uAIwNTIXF0HSP2h5owe0G-XS3lL43ZFITzD7Ekl-lBU" 
WORKSHEET_CLIENTE_GID = None 

def autenticar_google_sheets():
    try:
        private_key = os.getenv("GOOGLE_PRIVATE_KEY")
        client_email = os.getenv("GOOGLE_CLIENT_EMAIL")
        
        if not private_key or not client_email: 
            logger.warning("⚠️ Falta GOOGLE_PRIVATE_KEY o GOOGLE_CLIENT_EMAIL.")
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
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        return gspread.authorize(creds)
    except Exception as e:
        logger.error(f"❌ Error crítico autenticando Google Sheets: {str(e)}", exc_info=True)
        return None

def obtener_datos_sheet(spreadsheet_id: str, worksheet_gid: int = None):
    try:
        client = autenticar_google_sheets()
        if not client: return []
        
        try:
            sh = client.open_by_key(spreadsheet_id)
        except Exception as e:
            logger.error(f"❌ Error abriendo hoja {spreadsheet_id}: {e}")
            return []

        worksheet = None
        if worksheet_gid:
            try:
                worksheet = sh.get_worksheet_by_id(worksheet_gid)
            except Exception: pass
        
        if not worksheet: worksheet = sh.sheet1

        data = worksheet.get_all_values()
        if len(data) < 2: return []

        header_idx = 0
        for i, row in enumerate(data[:8]): 
            row_lower = [str(c).lower() for c in row]
            if any(k in row_lower for k in ["motivo", "título", "titulo", "evento", "fecha"]):
                header_idx = i
                break
        
        headers = data[header_idx]
        rows = data[header_idx+1:]
        
        res = []
        for r in rows:
            if not any(r): continue 
            if len(r) < len(headers): r += [""] * (len(headers) - len(r))
            fila_dict = dict(zip(headers, r))
            res.append(fila_dict)
            
        return res
    except Exception as e:
        logger.error(f"Error general leyendo sheet: {e}")
        return []

# --- LOGICA DE PROCESAMIENTO SEPARADA ---

def procesar_fila_cliente(fila):
    """Normaliza solo las filas de la gestión interna"""
    f_map = {k.lower().strip(): v for k, v in fila.items()}
    
    # --- CORRECCIÓN: Búsqueda flexible de la columna Costo ---
    costo_encontrado = "0"
    for key, value in f_map.items():
        # Busca palabras clave comunes si el nombre exacto falla
        if any(palabra in key for palabra in ["costo", "precio", "valor", "monto", "importe", "presupuesto"]):
            if value and str(value).strip(): # Si tiene valor
                costo_encontrado = value
                break

    return {
        "FECHA": f_map.get("fecha de salida viaje") or f_map.get("fecha", ""),
        "MOTIVO / EVENTO": f_map.get("motivo") or f_map.get("evento") or "Sin título",
        "LUGAR": f_map.get("lugar") or f_map.get("destino", ""),
        "INSTITUCIÓN": f_map.get("institución") or f_map.get("institucion", ""),
        "NOMBRE": f_map.get("nombre", ""),
        
        # Usamos el valor encontrado dinámicamente
        "COSTO": costo_encontrado, 
        
        "EE": f_map.get("ee", ""),
        "ESTADO": f_map.get("estado", ""),
        "RENDICIÓN": f_map.get("rendición") or f_map.get("rendicion", ""),
        "F. REGRESO": f_map.get("fecha de regreso del viaje", ""),
    }

def procesar_fila_ministerio(fila):
    """Normaliza solo las filas de la agenda oficial"""
    f_map = {k.lower().strip(): v for k, v in fila.items()}
    fecha = next((v for k,v in f_map.items() if "fecha" in k), "")
    evento = next((v for k,v in f_map.items() if "título" in k or "evento" in k), "Evento Oficial")
    lugar = next((v for k,v in f_map.items() if "lugar" in k or "ubicación" in k), "")
    hora = next((v for k,v in f_map.items() if "hora" in k), "")
    
    return {
        "FECHA": fecha,
        "HORA": hora,
        "EVENTO": evento,
        "LUGAR": lugar
    }

# --- FUNCIONES EXPORTADAS PARA MAIN.PY ---

def get_data_cliente_formatted():
    raw = obtener_datos_sheet(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
    return [procesar_fila_cliente(r) for r in raw]

def get_data_ministerio_formatted():
    raw = obtener_datos_sheet(SHEET_MINISTERIO_ID, WORKSHEET_MINISTERIO_GID)
    return [procesar_fila_ministerio(r) for r in raw]

def obtener_datos_raw():
    """Función legacy para compatibilidad si se necesitara unir"""
    return get_data_cliente_formatted() + get_data_ministerio_formatted()

# --- TOOLS DEL AGENTE ---
@tool
def consultar_calendario_ministerio(consulta: str):
    """Consulta la agenda pública del ministerio."""
    return json.dumps(obtener_datos_sheet(SHEET_MINISTERIO_ID, WORKSHEET_MINISTERIO_GID))

@tool
def consultar_calendario_cliente(consulta: str):
    """Consulta la agenda de gestión interna."""
    return json.dumps(obtener_datos_sheet(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID))

@tool
def consultar_calendario(consulta: str):
    """Consulta la agenda general.""" 
    return consultar_calendario_ministerio(consulta)