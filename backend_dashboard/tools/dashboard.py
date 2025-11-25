import os
import json
import gspread
from google.oauth2 import service_account
from langchain.tools import tool

# --- CONFIGURACIÓN ---
SPREADSHEET_ID = "1Sm2icTOvSbmGD7mdUtl2DfflUZqoHpBW"
WORKSHEET_GID = 563858184  # Hoja Calendario Internacional

def autenticar_google_sheets():
    """
    Autenticación con Google Sheets usando Service Account desde variables de entorno.
    """
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    try:
        private_key = os.getenv("GOOGLE_PRIVATE_KEY")
        client_email = os.getenv("GOOGLE_CLIENT_EMAIL")

        if not private_key or not client_email:
            print("⚠️ ERROR: Credenciales de Google no encontradas en las variables de entorno.")
            return None

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

        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=scope
        )

        return gspread.authorize(creds)

    except Exception as e:
        print(f"❌ Error en autenticación: {str(e)}")
        return None


def obtener_datos_raw():
    """
    Lee datos desde la hoja específica del Spreadsheet definida por GID.
    """
    try:
        client = autenticar_google_sheets()
        if not client:
            return []

        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.get_worksheet_by_id(WORKSHEET_GID)

        data = sheet.get_all_values()
        if len(data) < 2:
            print("⚠️ Hoja sin datos suficientes.")
            return []

        headers = data[1]  # Segunda fila
        filas = data[2:]    # Desde la tercera fila

        resultados = []

        for row in filas:
            if any(row):
                row = row[:len(headers)]
                resultados.append(dict(zip(headers, row)))

        print(f"✔ Datos cargados: {len(resultados)} filas")
        return resultados

    except Exception as e:
        print(f"❌ Error al leer los datos: {str(e)}")
        return []


@tool
def consultar_calendario(consulta: str):
    """
    Herramienta para consultar agenda y eventos del calendario.
    """
    try:
        print("🔍 Ejecutando herramienta consultar_calendario()...")
        datos = obtener_datos_raw()

        if not datos:
            return "No se pudieron obtener datos del calendario."

        return json.dumps(datos[:15], indent=2, ensure_ascii=False)

    except Exception as e:
        return f"Excepción en herramienta: {str(e)}"
