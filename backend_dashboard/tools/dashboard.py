import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from langchain.tools import tool

# TU ID EXACTO
SPREADSHEET_ID = "1VNQrU8tvzZnNKTXvKtNNFtkkXAeuAM4TTCPlcEeLN88"

def autenticar_google_sheets():
    """Autentica y devuelve el cliente con FIX de saltos de línea"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    posibles_rutas = ["service_account.json", "../service_account.json", "backend_dashboard/service_account.json"]
    creds_file = None
    
    for ruta in posibles_rutas:
        if os.path.exists(ruta):
            creds_file = ruta
            break
            
    if not creds_file:
        print("⚠️ No se encontró el archivo service_account.json")
        return None
        
    try:
        # --- EL FIX MÁGICO ---
        # 1. Leemos el archivo manualmente como JSON
        with open(creds_file, "r") as f:
            creds_dict = json.load(f)

        # 2. Buscamos la clave privada y forzamos que los saltos de línea sean reales
        # Esto arregla el error "Invalid JWT Signature" si se rompió al copiar/pegar
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        # 3. Autenticamos usando el diccionario corregido (no el archivo directo)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
        
    except Exception as e:
        print(f"Error crítico en autenticación: {e}")
        return None

def obtener_datos_raw():
    """Función para la tabla visual"""
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
    """Herramienta para el Agente (IA)"""
    try:
        datos = obtener_datos_raw()
        if not datos: return "El calendario está vacío o hubo un error de lectura."
        
        muestra = datos[:15]
        return f"Datos del Calendario:\n{json.dumps(muestra, indent=2, ensure_ascii=False)}"
    except Exception as e:
        return f"Error: {str(e)}"