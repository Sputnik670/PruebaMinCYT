import os
import json
import gspread
import io 
import csv 
from google.oauth2 import service_account
from googleapiclient.discovery import build 
from langchain.tools import tool

# --- CONFIGURACIÓN ---
SPREADSHEET_ID = "1Sm2icTOvSbmGD7mdUtl2DfflUZqoHpBW"

def autenticar_google_sheets():
    """
    Autentica con Google Sheets/Drive usando variables de entorno.
    Devuelve un cliente gspread que contiene las credenciales necesarias.
    """
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    try:
        private_key = os.getenv("GOOGLE_PRIVATE_KEY")
        client_email = os.getenv("GOOGLE_CLIENT_EMAIL")

        # --- DEBUG: Imprimir info en los logs de Render para verificar ---
        if private_key:
            print(f"--- DEBUG AUTH ---")
            print(f"Email: {client_email}")
            print(f"Longitud Clave: {len(private_key)}")
            print(f"Inicio Clave: >{private_key[:10]}<") 
            print(f"Fin Clave: >{private_key[-10:]}<")
            print(f"--- FIN DEBUG ---")
        else:
            print("⚠️ ERROR CRÍTICO: No se leyó la variable GOOGLE_PRIVATE_KEY")
            return None

        if not private_key or not client_email:
            return None

        # El .replace('\\n', '\n') es vital
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
            creds_dict, 
            scopes=scope
        )
        
        # Necesitamos el cliente gspread para obtener las credenciales, pero ya no lo usamos para leer
        return gspread.authorize(creds) 

    except Exception as e:
        print(f"❌ Error fatal en autenticación: {str(e)}")
        return None

def obtener_datos_raw():
    """
    Solución robusta para XLSX: Usa la API de Drive para descargar el archivo 
    como CSV y luego lo procesa, evitando el error 400 de formato.
    """
    try:
        # La función de autenticación devuelve el cliente gspread
        client = autenticar_google_sheets()
        if not client: return []
        
        # OBTENER CREDENCIALES: CORRECCIÓN DEL ERROR DE ATRIBUTO
        creds = client.auth  # <--- ¡CORRECCIÓN CLAVE AQUÍ!

        # 1. Inicializar el servicio de Drive para manejar el archivo XLSX
        service = build('drive', 'v3', credentials=creds)

        # 2. Exportar el archivo XLSX (usando SPREADSHEET_ID como File ID) a formato CSV
        file_id = SPREADSHEET_ID 
        request = service.files().export_media(fileId=file_id, 
                                              mimeType='text/csv')
        
        # 3. Descargar el contenido y procesar el CSV
        downloaded_file = request.execute()
        file_io = io.StringIO(downloaded_file.decode('utf-8'))
        reader = csv.reader(file_io)
        
        # Extraer filas
        data = list(reader)
        if not data or len(data) < 2:
            return []
        
        # 4. Mapear datos (Encabezados en Fila 2 - índice 1)
        headers = [h for h in data[1] if h] 
        data_rows = data[2:]
        results = []
        
        for row in data_rows:
            if any(row):
                processed_row = row[:len(headers)]
                if len(processed_row) == len(headers):
                    results.append(dict(zip(headers, processed_row)))
        
        return results

    except Exception as e:
        print(f"❌ Error leyendo datos con Drive API: {str(e)}")
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