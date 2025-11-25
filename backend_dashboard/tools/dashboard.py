import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
import base64
from langchain.tools import tool

# TU ID EXACTO (Confirmado)
SPREADSHEET_ID = "1Sm2icTOvSbmGD7mdUtl2DfflUZqoHpBW"

def autenticar_google_sheets():
    """Autentica usando la variable de entorno BASE64 con corrección de saltos de línea"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # 1. Buscamos la variable blindada
        creds_base64 = os.getenv("GOOGLE_CREDENTIALS_BASE64")
        
        if not creds_base64:
            print("⚠️ Error: No existe la variable GOOGLE_CREDENTIALS_BASE64")
            return None
            
        # 2. La desciframos (De Base64 a JSON texto)
        creds_json_str = base64.b64decode(creds_base64).decode("utf-8")
        
        # 3. La convertimos a Diccionario
        creds_dict = json.loads(creds_json_str)
        
        # --- EL FIX DE ORO ---
        # Esto busca los "\n" falsos y los convierte en Enters reales.
        # Es OBLIGATORIO si el Base64 se generó en Windows.
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        # 4. Autenticamos
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
        
    except Exception as e:
        print(f"Error crítico desencriptando credenciales: {e}")
        return None

def obtener_datos_raw():
    """Función para obtener los datos crudos (para la tabla visual)"""
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