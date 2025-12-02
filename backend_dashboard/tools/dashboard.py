import os
import json
import gspread
import logging
from google.oauth2 import service_account
from langchain.tools import tool
from cachetools import TTLCache, cached

# Configurar Logger específico para este módulo
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DE TABLAS (GOOGLE SHEETS) ---
SHEET_MINISTERIO_ID = "1lkViCdCeq7F4yEHVdbjfrV-G7KvKP6TZfxsOc-Ov4xI"
WORKSHEET_MINISTERIO_GID = 563858184

SHEET_CLIENTE_ID = "1uAIwNTIXF0HSP2h5owe0G-XS3lL43ZFITzD7Ekl-lBU" 
WORKSHEET_CLIENTE_GID = None 

# --- CONFIGURACIÓN DE CACHÉ (OPTIMIZACIÓN) ---
# Guardamos los resultados por 10 minutos (600 segundos)
cache_agenda = TTLCache(maxsize=5, ttl=600)

def autenticar_google_sheets():
    try:
        private_key = os.getenv("GOOGLE_PRIVATE_KEY")
        client_email = os.getenv("GOOGLE_CLIENT_EMAIL")
        
        if not private_key or not client_email: 
            logger.warning("⚠️ Falta GOOGLE_PRIVATE_KEY o GOOGLE_CLIENT_EMAIL.")
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
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        return gspread.authorize(creds)
    except Exception as e:
        logger.error(f"❌ Error crítico autenticando Google Sheets: {str(e)}", exc_info=True)
        return None

def obtener_datos_sheet(spreadsheet_id: str, worksheet_gid: int = None):
    """
    Función pura que realiza la petición real a Google Sheets API.
    """
    try:
        logger.info(f"📡 Conectando a Google Sheets: {spreadsheet_id} (Sin caché)")
        client = autenticar_google_sheets()
        if not client: return []
        
        try:
            sh = client.open_by_key(spreadsheet_id)
        except Exception as e:
            logger.error(f"❌ Error abriendo hoja {spreadsheet_id}: {e}")
            return []

        worksheet = None
        if worksheet_gid:
            try:
                worksheet = sh.get_worksheet_by_id(worksheet_gid)
            except Exception: pass
        
        if not worksheet: worksheet = sh.sheet1

        data = worksheet.get_all_values()
        if len(data) < 2: return []

        # Detección inteligente de cabecera (busca palabras clave en las primeras 8 filas)
        header_idx = 0
        for i, row in enumerate(data[:8]): 
            row_lower = [str(c).lower() for c in row]
            if any(k in row_lower for k in ["motivo", "título", "titulo", "evento", "fecha"]):
                header_idx = i
                break
        
        headers = data[header_idx]
        rows = data[header_idx+1:]
        
        res = []
        for r in rows:
            if not any(r): continue 
            if len(r) < len(headers): r += [""] * (len(headers) - len(r))
            fila_dict = dict(zip(headers, r))
            res.append(fila_dict)
            
        return res
    except Exception as e:
        logger.error(f"Error general leyendo sheet: {e}")
        return []

# --- WRAPPER CON CACHÉ ---
@cached(cache_agenda)
def obtener_datos_sheet_cached(spreadsheet_id: str, worksheet_gid: int = None):
    return obtener_datos_sheet(spreadsheet_id, worksheet_gid)

# --- LÓGICA DE PROCESAMIENTO INTELIGENTE (MEJORA 3) ---

def buscar_valor_inteligente(fila_map, keywords_primarias, keywords_secundarias=None):
    """
    Busca un valor en el diccionario 'fila_map' probando múltiples variantes de nombres de columna.
    Prioriza keywords_primarias (coincidencia fuerte) y luego secundarias (coincidencia parcial).
    """
    # 1. Búsqueda exacta o contenida fuerte
    for key, value in fila_map.items():
        if any(p == key for p in keywords_primarias): # Exacta (ej: 'fecha')
            return value
        if any(f" {p} " in f" {key} " for p in keywords_primarias): # Palabra completa contenida
            return value

    # 2. Búsqueda parcial (contiene la palabra)
    match_secundario = None
    all_keywords = keywords_primarias + (keywords_secundarias or [])
    
    for key, value in fila_map.items():
        if any(p in key for p in all_keywords):
            # Guardamos el primer match pero seguimos buscando por si hay uno mejor
            if not match_secundario and value: 
                match_secundario = value
    
    return match_secundario or ""

def procesar_fila_cliente(fila):
    """
    Normaliza las filas de gestión interna usando BÚSQUEDA DIFUSA.
    Esto hace al sistema resistente a cambios de nombres en el Excel.
    """
    # Normalizamos claves a minúsculas y sin espacios extra
    f_map = {str(k).lower().strip(): v for k, v in fila.items()}
    
    # 1. Costo (Prioridad financiera)
    costo = buscar_valor_inteligente(f_map, 
        ["costo", "precio", "monto", "valor", "importe", "total"], 
        ["presupuesto", "gasto"]
    ) or "0"

    # 2. Fecha Ida / Salida
    fecha = buscar_valor_inteligente(f_map, 
        ["fecha de salida", "fecha salida", "fecha ida", "salida"], 
        ["fecha", "día", "date"]
    )

    # 3. Fecha Regreso
    fecha_regreso = buscar_valor_inteligente(f_map, 
        ["fecha de regreso", "fecha regreso", "fecha vuelta", "regreso", "vuelta"],
        ["fin"]
    )

    # 4. Motivo
    motivo = buscar_valor_inteligente(f_map,
        ["motivo", "evento", "descripción", "actividad", "asunto"],
        ["título", "nombre"]
    ) or "Sin título"

    # 5. Lugar
    lugar = buscar_valor_inteligente(f_map,
        ["lugar", "destino", "ciudad", "ubicación", "provincia"],
        ["sitio", "zona"]
    )

    # 6. Institución / Pasajero
    institucion = buscar_valor_inteligente(f_map,
        ["institución", "institucion", "organismo", "empresa"],
        ["quien", "pasajero", "solicitante"]
    )

    # 7. Estado
    estado = buscar_valor_inteligente(f_map, ["estado", "status", "situación"], [])
    rendicion = buscar_valor_inteligente(f_map, ["rendición", "rendicion", "expediente"], ["ee", "ex"])

    return {
        "FECHA": fecha,
        "MOTIVO / EVENTO": motivo,
        "LUGAR": lugar,
        "INSTITUCIÓN": institucion,
        "COSTO": costo, 
        "ESTADO": estado,
        "RENDICIÓN": rendicion,
        "F. REGRESO": fecha_regreso,
    }

def procesar_fila_ministerio(fila):
    """Normaliza la agenda oficial también con lógica difusa"""
    f_map = {str(k).lower().strip(): v for k, v in fila.items()}
    
    return {
        "FECHA": buscar_valor_inteligente(f_map, ["fecha", "día"], ["cuándo"]),
        "HORA": buscar_valor_inteligente(f_map, ["hora", "horario"], ["hs"]),
        "EVENTO": buscar_valor_inteligente(f_map, ["evento", "título", "actividad"], ["qué"]),
        "LUGAR": buscar_valor_inteligente(f_map, ["lugar", "ubicación"], ["dónde"])
    }

# --- FUNCIONES EXPORTADAS PARA MAIN.PY (USANDO CACHÉ) ---

def get_data_cliente_formatted():
    raw = obtener_datos_sheet_cached(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
    return [procesar_fila_cliente(r) for r in raw]

def get_data_ministerio_formatted():
    raw = obtener_datos_sheet_cached(SHEET_MINISTERIO_ID, WORKSHEET_MINISTERIO_GID)
    return [procesar_fila_ministerio(r) for r in raw]

def obtener_datos_raw():
    return get_data_cliente_formatted() + get_data_ministerio_formatted()

# --- TOOLS DEL AGENTE (USANDO CACHÉ) ---

@tool
def analizar_estructura_tablas(consulta: str):
    """
    Herramienta de diagnóstico para ver qué columnas está detectando realmente el sistema.
    """
    try:
        raw_data = obtener_datos_sheet_cached(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
        if not raw_data:
            return "No se pudieron leer datos de la planilla."
        
        columnas = list(raw_data[0].keys())
        ejemplo = raw_data[0]
        
        return f"""
        --- ESTRUCTURA ORIGINAL (GOOGLE SHEETS) ---
        Columnas: {', '.join(columnas)}
        Ejemplo Raw: {json.dumps(ejemplo, indent=2, ensure_ascii=False)}
        """
    except Exception as e:
        return f"Error analizando estructura: {e}"

@tool
def consultar_calendario_ministerio(consulta: str):
    """Agenda Pública / Oficial del Ministro."""
    return json.dumps(get_data_ministerio_formatted(), ensure_ascii=False)

@tool
def consultar_calendario_cliente(consulta: str):
    """
    Agenda de Gestión Interna (Logística, Viajes).
    Usa esta herramienta para ver listados crudos. Para cálculos, usa el analista.
    """
    return json.dumps(get_data_cliente_formatted(), ensure_ascii=False)