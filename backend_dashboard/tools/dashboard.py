import os
import json
import gspread
from google.oauth2 import service_account
from langchain.tools import tool

# ID del Sheet Nativo (el que creamos y funcionaba)
SPREADSHEET_ID = "1lkViCdCeq7F4yEHVdbjfrV-G7KvKP6TZfxsOc-Ov4xI"
WORKSHEET_GID = 563858184

def autenticar_google_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
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
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email}"
        }
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"Error Auth Google: {e}")
        return None

def obtener_datos_raw():
    print(f"--- LEYENDO GOOGLE SHEET ---")
    try:
        client = autenticar_google_sheets()
        if not client: return []
        
        sh = client.open_by_key(SPREADSHEET_ID)
        # Intento robusto de obtener hoja
        try:
            worksheet = sh.get_worksheet_by_id(WORKSHEET_GID)
            if not worksheet: worksheet = sh.sheet1
        except:
            worksheet = sh.sheet1

        data = worksheet.get_all_values()
        if len(data) < 2: return []

        # Buscador de encabezados simple
        header_idx = 0
        for i, row in enumerate(data[:5]):
            row_s = [str(c).lower() for c in row]
            if "título" in row_s or "titulo" in row_s:
                header_idx = i
                break
        
        headers = data[header_idx]
        rows = data[header_idx+1:]
        
        res = []
        for r in rows:
            if not any(r): continue
            # Normalizar longitud
            if len(r) < len(headers): r += [""]*(len(headers)-len(r))
            res.append(dict(zip(headers, r)))
            
        return res
    except Exception as e:
        print(f"Error Sheet: {e}")
        return []

@tool
def consultar_calendario(consulta: str):
    """Consulta la agenda/calendario del ministerio."""
    data = obtener_datos_raw()
    # Limitamos a 10 para no saturar la memoria del modelo gratis
    return json.dumps(data[:10], ensure_ascii=False)