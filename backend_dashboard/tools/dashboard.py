import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from langchain.tools import tool

# TU ID DEL EXCEL
SPREADSHEET_ID = "1VNQrU8tvzZnNKTXvKtNNFtkkXAeuAM4TTCPlcEeLN88"

def autenticar_google_sheets():
    """Autentica y devuelve el cliente de gspread"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    posibles_rutas = ["service_account.json", "../service_account.json", "backend_dashboard/service_account.json"]
    creds_file = None
    
    for ruta in posibles_rutas:
        if os.path.exists(ruta):
            creds_file = ruta
            break
            
    if not creds_file:
        return None
        
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
    client = gspread.authorize(creds)
    return client

def obtener_datos_raw():
    """Función auxiliar para traer los datos limpios (Lista de Diccionarios)"""
    try:
        client = autenticar_google_sheets()
        if not client:
            return []
        
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        # get_all_records devuelve una lista de dicts: [{'Fecha': '...', 'Evento': '...'}, ...]
        return sheet.get_all_records()
    except Exception as e:
        print(f"Error leyendo sheet: {e}")
        return []

@tool
def consultar_calendario(consulta: str):
    """Herramienta para el Agente (IA)"""
    try:
        datos = obtener_datos_raw()
        if not datos:
            return "El calendario está vacío o hubo un error de lectura."

        # Tomamos los primeros 15 para la IA
        muestra = datos[:15]
        return f"Datos del Calendario:\n{json.dumps(muestra, indent=2, ensure_ascii=False)}"
    except Exception as e:
        return f"Error: {str(e)}"