import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from langchain.tools import tool

# TU ID EXACTO
SPREADSHEET_ID = "1Sm2icTOvSbmGD7mdUtl2DfflUZqoHpBW"

def autenticar_google_sheets():
    """
    Autentica construyendo el diccionario de credenciales manualmente 
    desde variables de entorno individuales. (A prueba de fallos de JSON)
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # 1. Leemos las variables sueltas
        private_key = os.getenv("GOOGLE_PRIVATE_KEY")
        client_email = os.getenv("GOOGLE_CLIENT_EMAIL")
        
        if not private_key or not client_email:
            print("⚠️ Faltan las variables GOOGLE_PRIVATE_KEY o GOOGLE_CLIENT_EMAIL")
            return None

        # 2. Construimos el diccionario en memoria
        # IMPORTANTE: El .replace es vital para arreglar el formato que viene de Render
        creds_dict = {
            "type": "service_account",
            "project_id": "dashboard-impacto-478615", # No es critico para auth, pero lo ponemos
            "private_key_id": "cualquier_id", # No es critico
            "private_key": private_key.replace("\\n", "\n"),
            "client_email": client_email,
            "client_id": "116197238257458301101", # No es critico
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email.replace('@', '%40')}"
        }
        
        # 3. Autenticamos
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
        
    except Exception as e:
        print(f"Error crítico autenticando: {e}")
        return None

def obtener_datos_raw():
    try:
        client = autenticar_google_sheets()
        if not client: return []
        
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        return sheet.get_all_records()
    except Exception as e:
        print(f"Error leyendo sheet: {e}")
        return []

@tool
def consultar_calendario(consulta: str):
    """
    Usa esta herramienta para consultar la agenda, eventos, fechas 
    y lugares del calendario internacional del Ministerio.
    """
    try:
        datos = obtener_datos_raw()
        if not datos: return "El calendario está vacío."
        
        muestra = datos[:15]
        return f"Datos del Calendario:\n{json.dumps(muestra, indent=2, ensure_ascii=False)}"
    except Exception as e:
        return f"Error: {str(e)}"