import os
import logging
import hashlib
import io
import re
import pandas as pd
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("sync_service")

# --- CONFIGURACIÓN DE FUENTES ---
# Agregamos ambos IDs aquí con una etiqueta para identificar el origen
SOURCES = [
    {
        "id": "1HOiSJ-Hugkddv-kwGax6vhSV9tzthkiz", 
        "name": "Gestión Interna", 
        "default_ambito": "Gestión"
    },
    {
        "id": "1Sm2icTOvSbmGD7mdUtl2DfflUZqoHpBW", 
        "name": "Agenda Oficial", 
        "default_ambito": "Oficial"
    }
]

SUPA_URL = os.getenv("SUPABASE_URL")
SUPA_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

MESES_ES = {
    'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04', 'mayo': '05', 'junio': '06',
    'julio': '07', 'agosto': '08', 'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12',
    'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04', 'may': '05', 'jun': '06',
    'jul': '07', 'ago': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dic': '12'
}

# --- HELPERS ---

def get_drive_service():
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
        }
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        logger.error(f"❌ Error Auth: {e}")
        return None

def generar_id_unico(fecha, titulo, funcionario):
    raw = f"{fecha}{titulo}{funcionario}".strip().lower()
    return hashlib.md5(raw.encode()).hexdigest()

def limpiar_moneda(texto):
    if pd.isna(texto) or not texto: return "USD 0.00"
    texto = str(texto).strip().upper()
    moneda = "USD"
    if "EUR" in texto or "€" in texto: moneda = "EUR"
    elif "ARS" in texto or "PESO" in texto: moneda = "ARS"
    solo_nums = re.sub(r'[^\d.,]', '', texto)
    try:
        if ',' in solo_nums and '.' in solo_nums:
            if solo_nums.find(',') < solo_nums.find('.'): solo_nums = solo_nums.replace(',', '') 
            else: solo_nums = solo_nums.replace('.', '').replace(',', '.')
        elif ',' in solo_nums:
             partes = solo_nums.split(',')
             if len(partes[-1]) == 2: solo_nums = solo_nums.replace(',', '.')
             else: solo_nums = solo_nums.replace(',', '')
        val = float(solo_nums)
        return f"{moneda} {val:.2f}"
    except: return f"{moneda} 0.00"

def normalizar_fecha(fecha_raw, anio_hoja):
    if pd.isna(fecha_raw) or not fecha_raw: return None
    if isinstance(fecha_raw, (pd.Timestamp, datetime)): return fecha_raw.strftime("%Y-%m-%d")
    
    texto = str(fecha_raw).strip().lower()
    if not texto or texto in ["nan", "pendiente", "a confirmar"]: return None
    if " " in texto and ":" in texto: texto = texto.split(" ")[0]

    anio_contexto = "2024"
    match_anio = re.search(r'20\d{2}', str(anio_hoja))
    if match_anio: anio_contexto = match_anio.group(0)

    try:
        match_rango = re.search(r'(\d{1,2})\s*(?:al|a|-|y|&)\s*\d{1,2}[/-](\d{1,2})', texto)
        if match_rango:
            return f"{anio_contexto}-{int(match_rango.group(2)):02d}-{int(match_rango.group(1)):02d}"

        for mes_es, mes_num in MESES_ES.items():
            if mes_es in texto:
                texto = texto.replace(mes_es, mes_num)
                if str(anio_contexto) not in texto: texto = f"{texto}/{anio_contexto}"
                break 

        dt = pd.to_datetime(texto, dayfirst=True, errors='coerce')
        if not pd.isna(dt): 
            if dt.year < 2020 or dt.year > 2030:
                return f"{anio_contexto}-{dt.month:02d}-{dt.day:02d}"
            return dt.strftime("%Y-%m-%d")
    except: pass
    return None

def descargar_excel_memoria(service, file_id):
    try:
        request = service.files().get_media(fileId=file_id)
        file_stream = io.BytesIO()
        downloader = MediaIoBaseDownload(file_stream, request)
        done = False
        while done is False: status, done = downloader.next_chunk()
        file_stream.seek(0)
        return file_stream
    except Exception as e:
        logger.error(f"❌ Error descarga ({file_id}): {e}")
        return None

# --- FUNCIÓN PRINCIPAL ---

def sincronizar_google_a_supabase():
    service = get_drive_service()
    if not service: return

    supabase = create_client(SUPA_URL, SUPA_KEY)
    total_global_sincronizado = 0

    # ITERAMOS SOBRE CADA ARCHIVO (GESTIÓN Y OFICIAL)
    for source in SOURCES:
        file_id = source["id"]
        source_name = source["name"]
        default_ambito = source["default_ambito"]

        try:
            print(f"\n📥 Procesando '{source_name}'...")
            excel_stream = descargar_excel_memoria(service, file_id)
            if not excel_stream: continue

            xls = pd.ExcelFile(excel_stream)
            
            # KEY MAP GLOBAL (Combina términos de Gestión y Oficial)
            key_map = {
                "FECHA": ["FECHA", "INICIO", "SALIDA", "DIA", "DESDE"], 
                "TITULO": ["MOTIVO", "EVENTO", "TITULO", "TEMA", "ACTIVIDAD", "NOMBRE"],
                "LUGAR": ["DESTINO", "LUGAR", "CIUDAD", "PAIS", "UBICACION"],
                "FUNCIONARIO": ["FUNCIONARIO", "NOMBRE", "PARTICIPANTE", "QUIEN", "APELLIDO"],
                "COSTO": ["COSTO", "PRECIO", "VALOR", "IMPORTE", "GASTO", "MONTO"],
                "EXP": ["EXPEDIENTE", "EE", "EXP", "SOLICITUD", "AUTORIZACION"],
                "INSTITUCION": ["INSTITUCION", "ORGANISMO", "EMPRESA", "INVITA", "ORGANIZADOR", "ORGANIZA"], # Added Organizador
                "AMBITO": ["AMBITO", "TIPO", "NACINTL"] # Added Ambito
            }

            print(f"   🔎 Pestañas encontradas: {xls.sheet_names}")

            for sheet_name in xls.sheet_names:
                if "copia" in sheet_name.lower(): continue
                
                # 1. Detectar Header
                df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, nrows=15)
                header_idx = -1
                
                for i, row in df_raw.iterrows():
                    row_str = " ".join(row.astype(str)).upper()
                    puntos = 0
                    if any(x in row_str for x in key_map["FECHA"]): puntos += 2
                    if any(x in row_str for x in key_map["TITULO"]): puntos += 1
                    if any(x in row_str for x in key_map["FUNCIONARIO"]): puntos += 1
                    if any(x in row_str for x in key_map["EXP"]): puntos += 1
                    
                    if puntos >= 2:
                        header_idx = i
                        break
                
                if header_idx == -1:
                    print(f"      ⚠️ Saltando '{sheet_name}': Sin estructura.")
                    continue

                # 2. Leer
                df = pd.read_excel(xls, sheet_name=sheet_name, header=header_idx).fillna("")
                df.columns = [str(c).upper().strip() for c in df.columns]
                
                col_indices = {}
                for key, keywords in key_map.items():
                    for col in df.columns:
                        if any(k in col for k in keywords):
                            if key not in col_indices: col_indices[key] = col
                            elif key == "FECHA" and ("SOLICITUD" in col_indices[key] or "AUTORIZA" in col_indices[key]) and "FECHA" in col:
                                 col_indices[key] = col
                            break
                
                # 3. Fallback Fecha
                usar_fecha_default = False
                fecha_default = None
                if "FECHA" not in col_indices:
                    match_anio = re.search(r'20\d{2}', str(sheet_name))
                    if match_anio:
                        anio = match_anio.group(0)
                        fecha_default = f"{anio}-01-01"
                        usar_fecha_default = True
                        print(f"      ℹ️ Usando fecha default {fecha_default} para '{sheet_name}'")
                    else:
                        print(f"      ❌ '{sheet_name}' omitida: Sin fecha.")
                        continue

                registros_unicos = {}
                
                for idx, row in df.iterrows():
                    # Fecha
                    if usar_fecha_default:
                        fecha_final = fecha_default
                    else:
                        raw_fecha = row[col_indices["FECHA"]]
                        fecha_final = normalizar_fecha(raw_fecha, sheet_name)
                    
                    if not fecha_final: continue

                    # Datos
                    titulo_raw = row[col_indices["TITULO"]] if "TITULO" in col_indices else "Actividad Oficial"
                    funcionario_raw = row[col_indices["FUNCIONARIO"]] if "FUNCIONARIO" in col_indices else "Funcionario"
                    
                    if not str(titulo_raw).strip(): titulo_raw = f"Actividad de {funcionario_raw}"
                    if usar_fecha_default: titulo_raw += " (Fecha Estimada)"

                    lugar = row[col_indices["LUGAR"]] if "LUGAR" in col_indices else ""
                    costo_raw = row[col_indices["COSTO"]] if "COSTO" in col_indices else ""
                    exp = row[col_indices["EXP"]] if "EXP" in col_indices else ""
                    inst = row[col_indices["INSTITUCION"]] if "INSTITUCION" in col_indices else ""
                    
                    # Ámbito (Lógica especial para leer NAC/INT)
                    ambito_final = default_ambito
                    if "AMBITO" in col_indices:
                        val_ambito = str(row[col_indices["AMBITO"]]).upper()
                        if "NAC" in val_ambito: ambito_final = "Nacional"
                        elif "INT" in val_ambito: ambito_final = "Internacional"

                    # Hash
                    salt = str(idx) 
                    id_hash = generar_id_unico(fecha_final, titulo_raw, funcionario_raw + salt)
                    
                    costo_limpio = limpiar_moneda(costo_raw)
                    try: monto_float = float(costo_limpio.split()[1])
                    except: monto_float = 0.0
                    moneda_detectada = costo_limpio.split()[0]

                    registros_unicos[id_hash] = {
                        "id_hash": id_hash,
                        "fecha": fecha_final,
                        "titulo": str(titulo_raw).strip()[:300],
                        "funcionario": str(funcionario_raw).strip()[:100],
                        "lugar": str(lugar).strip(),
                        "costo": monto_float,
                        "moneda": moneda_detectada,
                        "num_expediente": str(exp),
                        "organizador": str(inst),
                        "ambito": ambito_final,
                        "origen_dato": f"{source_name} - {sheet_name}",
                        "updated_at": datetime.now().isoformat()
                    }

                batch = list(registros_unicos.values())
                if batch:
                    try:
                        supabase.table("agenda_unificada").upsert(batch, on_conflict="id_hash").execute()
                        print(f"      💾 {sheet_name}: {len(batch)} registros.")
                        total_global_sincronizado += len(batch)
                    except Exception as e:
                        print(f"      ⚠️ Error SQL: {e}")

        except Exception as e:
            logger.error(f"❌ Error procesando {source_name}: {e}")

    print(f"\n✅ FIN DEL PROCESO. Total sincronizado: {total_global_sincronizado}")

if __name__ == "__main__":
    sincronizar_google_a_supabase()