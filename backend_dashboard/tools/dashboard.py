import os
import json
import gspread
from google.oauth2 import service_account
from langchain.tools import tool

# --- CONFIGURACIÓN ---
SPREADSHEET_ID = "1Sm2icTOvSbmGD7mdUtl2DfflUZqoHpBW"

def autenticar_google_sheets():
    """
    Autentica con Google Sheets usando variables de entorno de Render.
    Incluye corrección de formato de clave privada y logs de debug.
    """
    # 1. Definimos el alcance de permisos
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    try:
        # 2. Leemos las variables
        private_key = os.getenv("GOOGLE_PRIVATE_KEY")
        client_email = os.getenv("GOOGLE_CLIENT_EMAIL")

        # --- DEBUG: Imprimir info en los logs de Render para verificar ---
        if private_key:
            print(f"--- DEBUG AUTH ---")
            print(f"Email: {client_email}")
            print(f"Longitud Clave: {len(private_key)}")
            # Mostramos el inicio y fin para ver si hay comillas extra
            print(f"Inicio Clave: >{private_key[:10]}<") 
            print(f"Fin Clave: >{private_key[-10:]}<")
            print(f"--- FIN DEBUG ---")
        else:
            print("⚠️ ERROR CRÍTICO: No se leyó la variable GOOGLE_PRIVATE_KEY")
            return None
        # ---------------------------------------------------------------

        if not private_key or not client_email:
            return None

        # 3. Construimos el diccionario de credenciales
        # NOTA: El .replace('\\n', '\n') es vital para que funcione en Render
        creds_dict = {
            "type": "service_account",
            "project_id": "dashboard-impacto-478615",
            "private_key_id": "indefinido_por_seguridad", 
            "private_key": private_key.replace("\\n", "\n"), 
            "client_email": client_email,
            "client_id": "116197238257458301101",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email.replace('@', '%40')}"
        }

        # 4. Autenticamos
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, 
            scopes=scope
        )
        
        return gspread.authorize(creds)

    except Exception as e:
        print(f"❌ Error fatal en autenticación: {str(e)}")
        return None

def obtener_datos_raw():
    """
    Obtiene todos los registros de la Hoja 1, usando la Fila 2 como encabezado.
    """
    try:
        client = autenticar_google_sheets()
        if not client: return []
        
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        
        # Leemos los datos usando la Fila 2 (head=2) como títulos
        return sheet.get_all_records(head=2) 
        
    except Exception as e:
        print(f"❌ Error leyendo datos del sheet: {str(e)}")
        return []

@tool
def consultar_calendario(consulta: str):
    """
    Usa esta herramienta para consultar la agenda, eventos, fechas 
    y lugares del calendario internacional del Ministerio.
    """
    try:
        print(f"🔍 Ejecutando herramienta calendario...")
        datos = obtener_datos_raw()
        
        if not datos:
            return "Error: No se pudieron obtener datos del calendario (ver logs)."
        
        # Tomamos una muestra de 15 items para no saturar el chat
        muestra = datos[:15]
        return f"Datos del Calendario:\n{json.dumps(muestra, indent=2, ensure_ascii=False)}"
    
    except Exception as e:
        return f"Excepción en herramienta: {str(e)}"