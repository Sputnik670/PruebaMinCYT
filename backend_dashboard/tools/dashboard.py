import gspread
from google.oauth2 import service_account  # <--- Librería moderna
import os
import json
from langchain.tools import tool

# TU ID EXACTO
SPREADSHEET_ID = "1Sm2icTOvSbmGD7mdUtl2DfflUZqoHpBW"

def autenticar_google_sheets():
    """
    Autentica construyendo el diccionario de credenciales manualmente.
    """
    # Scope corregido para la librería moderna
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    try:
        private_key = os.getenv("GOOGLE_PRIVATE_KEY")
        client_email = os.getenv("GOOGLE_CLIENT_EMAIL")
        
        if not private_key or not client_email:
            print("⚠️ Faltan las variables GOOGLE_PRIVATE_KEY o GOOGLE_CLIENT_EMAIL")
            return None

        # Construimos el diccionario
        creds_dict = {
            "type": "service_account",
            "project_id": "dashboard-impacto-478615", 
            "private_key_id": "cualquier_id",
            "private_key": private_key.replace("\\n", "\n"), # <--- EL FIX IMPORTANTE
            "client_email": client_email,
            "client_id": "116197238257458301101",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        
        # Autenticamos con la librería moderna
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scope)
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
    Usa esta herramienta para consultar la agenda del calendario internacional.
    """
    try:
        datos = obtener_datos_raw()
        if not datos: return "El calendario está vacío."
        
        muestra = datos[:15]
        return f"Datos del Calendario:\n{json.dumps(muestra, indent=2, ensure_ascii=False)}"
    except Exception as e:
        return f"Error: {str(e)}"