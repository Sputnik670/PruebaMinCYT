import os
import json
import gspread
from google.oauth2 import service_account
from langchain.tools import tool

# --- CONFIGURACIÓN ---
SPREADSHEET_ID = "1Sm2icTOvSbmGD7mdUtl2DfflUZqoHpBW"
WORKSHEET_GID = 563858184  # ID de la pestaña específica

def autenticar_google_sheets():
    """Autenticación con Google Sheets usando variables de entorno."""
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        private_key = os.getenv("GOOGLE_PRIVATE_KEY")
        client_email = os.getenv("GOOGLE_CLIENT_EMAIL")
        
        if not private_key or not client_email:
            print("⚠️ ERROR: Faltan credenciales en .env")
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
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"❌ Error autenticación: {e}")
        return None

def obtener_datos_raw():
    """Recupera datos de la hoja y maneja errores de filas vacías."""
    print("--- INTENTANDO LEER GOOGLE SHEET ---")
    client = autenticar_google_sheets()
    if not client:
        return []

    try:
        # Abrir documento
        sh = client.open_by_key(SPREADSHEET_ID)
        
        # Intentar abrir la hoja por ID, si falla, abre la primera
        try:
            worksheet = sh.get_worksheet_by_id(WORKSHEET_GID)
            if not worksheet: raise Exception("Hoja no encontrada")
            print(f"✔ Pestaña '{worksheet.title}' cargada correctamente.")
        except:
            print(f"⚠️ No se encontró la hoja con ID {WORKSHEET_GID}, abriendo la primera hoja...")
            worksheet = sh.sheet1

        data = worksheet.get_all_values()
        
        if len(data) < 2:
            print("⚠️ La hoja está vacía o tiene muy pocos datos.")
            return []

        # --- LÓGICA INTELIGENTE DE ENCABEZADOS ---
        # Buscamos la fila que contiene "Título" o "Title" para usarla de encabezado
        header_index = 0
        for i, row in enumerate(data[:5]): # Mira las primeras 5 filas
            row_str = [str(c).lower() for c in row]
            if "título" in row_str or "titulo" in row_str or "evento" in row_str:
                header_index = i
                break
        
        print(f"ℹ️ Encabezados detectados en la fila {header_index + 1}")
        
        headers = data[header_index]
        filas = data[header_index + 1:]
        
        resultados = []
        for row in filas:
            # Filtramos filas totalmente vacías
            if not any(field.strip() for field in row):
                continue
            
            # Rellenar si la fila es más corta que los headers
            if len(row) < len(headers):
                row += [""] * (len(headers) - len(row))
            
            # Crear diccionario seguro
            item = {str(headers[i]): str(row[i]) for i in range(len(headers)) if i < len(row)}
            resultados.append(item)

        print(f"✔ Datos procesados: {len(resultados)} filas enviadas al frontend.")
        return resultados

    except Exception as e:
        print(f"❌ ERROR LEYENDO SHEET: {str(e)}")
        return []

@tool
def consultar_calendario(consulta: str):
    """Consulta eventos del calendario."""
    datos = obtener_datos_raw()
    return json.dumps(datos[:10], ensure_ascii=False)