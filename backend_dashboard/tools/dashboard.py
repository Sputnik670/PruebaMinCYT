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
        
        return gspread.authorize(creds)

    except Exception as e:
        print(f"❌ Error fatal en autenticación: {str(e)}")
        return None

def obtener_datos_raw():
    """
    Lee los datos crudos (sin encabezados automáticos) y los procesa, 
    usando la Fila 2 como encabezado de manera explícita para evitar errores de formato.
    """
    try:
        # Se asume que 'autenticar_google_sheets()' está definido en este archivo.
        client = autenticar_google_sheets()
        if not client: return []
        
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        
        # 1. Obtenemos TODOS los valores como lista de listas
        # Este método no se rompe por celdas combinadas.
        all_data = sheet.get_all_values()
        
        # Si la hoja está vacía o tiene menos de dos filas
        if not all_data or len(all_data) < 2:
            return []
            
        # 2. Definimos que los encabezados son la Fila 2 (índice 1)
        headers = [h for h in all_data[1] if h] # Solo tomamos encabezados no vacíos
        data_rows = all_data[2:] # Los datos empiezan desde la Fila 3 (índice 2)
        
        # 3. Mapeamos los datos y evitamos las filas vacías entre meses
        results = []
        for row in data_rows:
            # Solo procesa si la fila tiene algún dato
            if any(row): 
                # Mapeamos la fila de datos con los encabezados
                processed_row = row[:len(headers)]
                results.append(dict(zip(headers, processed_row)))
        
        return results

    except Exception as e:
        # Esto imprimirá el error real si no es de autenticación
        print(f"❌ Error leyendo datos del sheet (Método Robusto): {str(e)}")
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