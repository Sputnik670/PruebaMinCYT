import os
import json
import gspread
import logging
from google.oauth2 import service_account
from langchain.tools import tool

# Configurar Logger específico para este módulo
logger = logging.getLogger(__name__)

# ID del Google Sheet Nativo
SPREADSHEET_ID = "1lkViCdCeq7F4yEHVdbjfrV-G7KvKP6TZfxsOc-Ov4xI"
WORKSHEET_GID = 563858184

def autenticar_google_sheets():
    try:
        private_key = os.getenv("GOOGLE_PRIVATE_KEY")
        client_email = os.getenv("GOOGLE_CLIENT_EMAIL")
        
        if not private_key or not client_email: 
            logger.warning("⚠️ Falta GOOGLE_PRIVATE_KEY o GOOGLE_CLIENT_EMAIL en variables de entorno.")
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
        # PUNTO 7: Capturamos la excepción real y la logueamos
        logger.error(f"❌ Error crítico autenticando Google Sheets: {str(e)}", exc_info=True)
        return None

def obtener_datos_raw():
    try:
        client = autenticar_google_sheets()
        if not client: 
            logger.warning("No se pudo obtener el cliente de GSpread. Verifica credenciales.")
            return []
        
        # Abrir por ID
        sh = client.open_by_key(SPREADSHEET_ID)
        try:
            worksheet = sh.get_worksheet_by_id(WORKSHEET_GID)
            if not worksheet: 
                logger.info("Worksheet GID no encontrado, usando sheet1 por defecto.")
                worksheet = sh.sheet1
        except Exception as e:
            logger.warning(f"Error accediendo al worksheet por ID, intentando sheet1. Detalle: {e}")
            worksheet = sh.sheet1

        data = worksheet.get_all_values()
        if len(data) < 2: return []

        # Buscar encabezados
        header_idx = 0
        for i, row in enumerate(data[:5]):
            if any("título" in str(c).lower() for c in row):
                header_idx = i
                break
        
        headers = data[header_idx]
        rows = data[header_idx+1:]
        
        res = []
        for r in rows:
            if not any(r): continue
            if len(r) < len(headers): r += [""] * (len(headers) - len(r))
            res.append(dict(zip(headers, r)))
            
        return res
    except Exception as e:
        # PUNTO 6: Usamos logger en lugar de print
        logger.error(f"❌ Error obteniendo datos del Sheet: {str(e)}", exc_info=True)
        return []

@tool
def consultar_calendario(consulta: str):
    """Consulta la agenda del ministerio completa."""
    d = obtener_datos_raw()
    return json.dumps(d, ensure_ascii=False)