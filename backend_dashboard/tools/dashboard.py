import os
import json
import gspread
import logging
from google.oauth2 import service_account
from langchain.tools import tool

# Configurar Logger específico para este módulo
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN DE TABLAS (GOOGLE SHEETS) ---

# 1. Agenda Ministerio (La original)
SHEET_MINISTERIO_ID = "1lkViCdCeq7F4yEHVdbjfrV-G7KvKP6TZfxsOc-Ov4xI"
WORKSHEET_MINISTERIO_GID = 563858184

# 2. Agenda Cliente / Interna (La nueva)
SHEET_CLIENTE_ID = "1HOiSJ-Hugkddv-kwGax6vhSV9tzthkiz" 
WORKSHEET_CLIENTE_GID = None 

def autenticar_google_sheets():
    try:
        private_key = os.getenv("GOOGLE_PRIVATE_KEY")
        client_email = os.getenv("GOOGLE_CLIENT_EMAIL")
        
        if not private_key or not client_email: 
            logger.warning("⚠️ Falta GOOGLE_PRIVATE_KEY o GOOGLE_CLIENT_EMAIL en variables de entorno.")
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
    Función maestra para leer cualquier Google Sheet, buscando cabeceras automáticamente.
    """
    try:
        client = autenticar_google_sheets()
        if not client: 
            logger.warning("No se pudo obtener el cliente de GSpread. Verifica credenciales.")
            return []
        
        # Intentar abrir por ID
        try:
            sh = client.open_by_key(spreadsheet_id)
        except Exception as e:
            logger.error(f"❌ No se pudo abrir la hoja con ID {spreadsheet_id}. Error: {e}")
            return []

        # Intentar obtener worksheet específico o usar el primero por defecto
        worksheet = None
        if worksheet_gid:
            try:
                worksheet = sh.get_worksheet_by_id(worksheet_gid)
                if not worksheet: 
                    logger.info(f"Worksheet GID {worksheet_gid} no encontrado, usando sheet1.")
            except Exception as e:
                logger.warning(f"Error accediendo al worksheet por ID, intentando sheet1. Detalle: {e}")
        
        if not worksheet:
            worksheet = sh.sheet1

        data = worksheet.get_all_values()
        if len(data) < 2: return []

        # Buscar encabezados dinámicamente
        header_idx = 0
        for i, row in enumerate(data[:6]): 
            row_lower = [str(c).lower() for c in row]
            if any(key in row_lower for key in ["título", "titulo", "evento", "actividad", "fecha", "hora"]):
                header_idx = i
                break
        
        headers = data[header_idx]
        rows = data[header_idx+1:]
        
        res = []
        for r in rows:
            if not any(r): continue 
            if len(r) < len(headers): r += [""] * (len(headers) - len(r))
            res.append(dict(zip(headers, r)))
            
        return res

    except Exception as e:
        logger.error(f"❌ Error obteniendo datos del Sheet ({spreadsheet_id}): {str(e)}", exc_info=True)
        return []

# --- HERRAMIENTAS QUE USARÁ EL AGENTE ---

@tool
def consultar_calendario_ministerio(consulta: str):
    """
    Consulta la agenda OFICIAL o PÚBLICA del ministerio.
    Usa esta herramienta si el usuario pregunta por eventos de gobierno, oficiales o del ministerio.
    """
    d = obtener_datos_sheet(SHEET_MINISTERIO_ID, WORKSHEET_MINISTERIO_GID)
    return json.dumps(d, ensure_ascii=False)

@tool
def consultar_calendario_cliente(consulta: str):
    """
    Consulta la agenda INTERNA, PRIVADA o del CLIENTE.
    Usa esta herramienta si el usuario pregunta por 'mis reuniones', 'agenda interna', 'eventos del equipo' 
    o temas no públicos del ministerio.
    """
    if "PON_AQUI" in SHEET_CLIENTE_ID:
        return "⚠️ Error de configuración: El ID de la tabla del cliente no ha sido configurado."
        
    d = obtener_datos_sheet(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
    return json.dumps(d, ensure_ascii=False)

# Legacy
@tool
def consultar_calendario(consulta: str):
    """Consulta la agenda (función de compatibilidad)."""
    return consultar_calendario_ministerio(consulta)

def obtener_datos_raw():
    """
    Función helper para el endpoint /api/data.
    Descarga, NORMALIZA INTELIGENTEMENTE y combina las dos agendas.
    Crea una columna 'OTROS DATOS' para capturar información diferente entre hojas.
    """
    try:
        # --- Lógica de Normalización Flexible ---
        def normalizar_fila(fila_cruda, origen_etiqueta):
            # 1. Limpiar claves
            f_lower = {k.lower().strip(): v for k, v in fila_cruda.items()}
            
            # 2. Definir sinónimos para las columnas principales
            keys_fecha = ["fecha", "dia", "date"]
            keys_hora = ["hora", "horario", "time", "inicio"]
            keys_evento = ["título", "titulo", "evento", "actividad", "reunión", "reunion", "tema", "asunto"]
            keys_lugar = ["lugar", "ubicación", "ubicacion", "sala", "location", "donde"]

            # 3. Función para extraer el primer valor coincidente
            def get_val(keys_list):
                for k in keys_list:
                    if k in f_lower and f_lower[k]: return f_lower[k]
                return ""

            fecha = get_val(keys_fecha)
            hora = get_val(keys_hora)
            evento = get_val(keys_evento) or "Sin título"
            lugar = get_val(keys_lugar)

            # 4. DETECTAR DATOS EXTRA (Cajón de sastre)
            # Identificamos qué claves YA usamos para no repetirlas
            todas_claves_usadas = keys_fecha + keys_hora + keys_evento + keys_lugar
            
            extras = []
            for k, v in f_lower.items():
                # Si la columna tiene datos y NO es una de las principales (y no es 'origen' ni vacía)
                if k not in todas_claves_usadas and k != "origen" and v and str(v).strip():
                    # Formato bonito: "Link: zoom.us..." o "Notas: Importante"
                    extras.append(f"{k.title()}: {v}")
            
            # Unimos todo lo extra en un solo texto
            otros_datos = " | ".join(extras)

            # 5. Devolver la fila estándar para el Dashboard
            return {
                "FECHA": fecha,
                "HORA": hora,
                "EVENTO": evento,
                "LUGAR": lugar,
                "OTROS DATOS": otros_datos,  # <--- Aquí va toda la info diferente
                "ORIGEN": origen_etiqueta
            }

        # --- Ejecución ---
        raw_ministerio = obtener_datos_sheet(SHEET_MINISTERIO_ID, WORKSHEET_MINISTERIO_GID)
        datos_ministerio = [normalizar_fila(r, "🏛️ OFICIAL") for r in raw_ministerio]

        raw_cliente = obtener_datos_sheet(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
        datos_cliente = [normalizar_fila(r, "💼 CLIENTE") for r in raw_cliente]

        # Combinar (Cliente primero)
        return datos_cliente + datos_ministerio

    except Exception as e:
        logger.error(f"Error normalizando datos dashboard: {e}")
        return []