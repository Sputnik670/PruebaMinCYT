import os
import pandas as pd
import logging
from dotenv import load_dotenv
from supabase import create_client
from tools.dashboard import obtener_datos_sheet_cached, SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID, procesar_fila_cliente
from tools.analysis import parse_money_value  # <--- CORRECCIÓN DE IMPORTE

# Cargar entorno
load_dotenv()

# Configurar logs simples
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("Diagnostico")

print("\n" + "="*50)
print("🩺 INICIANDO DIAGNÓSTICO DEL SISTEMA")
print("="*50 + "\n")

# --- 1. PRUEBA DE BASE DE DATOS (MEMORIA) ---
print("👉 1. VERIFICANDO MEMORIA (SUPABASE)...")
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

# <--- LÓGICA DE DEBUG PARA LA CLAVE RECHAZADA --->
if key:
    # Imprime los primeros 5 caracteres y la longitud para asegurar que se leyó la clave completa
    print(f"   Key leída (Longitud: {len(key)}, Inicio: {key[:5]}...)") 
else:
    print("   Key leída: VACÍA") 
# <--- FIN LÓGICA DE DEBUG --->

if not url or not key:
    print("❌ ERROR: Faltan credenciales en .env")
else:
    try:
        sb = create_client(url, key)
        
        # A. Crear Sesión de Prueba
        print("   Intentando crear sesión de prueba...", end=" ")
        sesion_data = {"user_id": "test_diagnostico", "titulo_sesion": "Prueba Técnica"}
        res_sesion = sb.table("sesiones_chat").insert(sesion_data).execute()
        sesion_id = res_sesion.data[0]["id"]
        print(f"✅ OK (ID: {sesion_id})")
        
        # B. Guardar Mensaje
        print("   Intentando guardar mensaje...", end=" ")
        msg_data = {
            "sesion_id": sesion_id,
            "mensaje_usuario": "Hola Test",
            "respuesta_bot": "Respuesta Test"
        }
        sb.table("mensajes_sesion").insert(msg_data).execute()
        print("✅ OK")
        
        # C. Leer Historial
        print("   Intentando leer historial...", end=" ")
        hist = sb.table("mensajes_sesion").select("*").eq("sesion_id", sesion_id).execute()
        if len(hist.data) > 0:
            print(f"✅ OK (Recuperado: '{hist.data[0]['mensaje_usuario']}')")
            print("   🏆 CONCLUSIÓN MEMORIA: La base de datos FUNCIONA PERFECTO.")
            print("      (Si en el chat falla, el problema es 100% del navegador/frontend)")
        else:
            print("❌ ERROR: Se guardó pero no se pudo leer.")
            
        # Limpieza
        sb.table("sesiones_chat").delete().eq("id", sesion_id).execute()
        
    except Exception as e:
        print(f"\n❌ FALLÓ LA BASE DE DATOS: {e}")
        print("   Posible causa: Políticas RLS o credenciales incorrectas.")

# --- 2. PRUEBA DE DATOS (CÁLCULO) ---
print("\n" + "="*50)
print("👉 2. VERIFICANDO DATOS EXCEL (CÁLCULO)...")

try:
    raw_data = obtener_datos_sheet_cached(SHEET_CLIENTE_ID, WORKSHEET_CLIENTE_GID)
    if not raw_data:
        print("❌ ERROR: No se pudieron descargar datos de Google Sheets.")
    else:
        print(f"✅ Datos descargados: {len(raw_data)} filas encontradas.")
        
        # Procesamos con la lógica actual del dashboard
        data_limpia = [procesar_fila_cliente(r) for r in raw_data]
        df = pd.DataFrame(data_limpia)
        
        print("\n🔎 ESTRUCTURA DE TUS DATOS (Primeras 3 filas):")
        cols_clave = ['FECHA', 'MOTIVO / EVENTO', 'COSTO']
        # Mostramos solo las que existan
        cols_existentes = [c for c in cols_clave if c in df.columns] or df.columns[:5]
        
        print(df[cols_existentes].head(3).to_string())
        
        print("\n🧮 PRUEBA DE LIMPIEZA DE DINERO:")
        if 'COSTO' in df.columns:
            # Tomamos 5 valores de ejemplo no vacíos
            ejemplos = df[df['COSTO'].astype(str).str.len() > 2]['COSTO'].head(5).tolist()
            if not ejemplos:
                 print("⚠️ No hay valores de costo no vacíos para probar.")
            for val in ejemplos:
                moneda, monto = parse_money_value(val)
                print(f"   Original: '{val}'  ->  Limpio ({moneda}): ${monto:,.2f}")
                
        else:
            print("❌ ERROR CRÍTICO: No encuentro la columna 'COSTO' ni parecida.")
            print("   Columnas detectadas:", df.columns.tolist())

        print("\n📅 PRUEBA DE FECHAS:")
        if 'FECHA' in df.columns:
            # Se usa errors='coerce' y dayfirst=True para intentar manejar formatos variados
            df['FECHA_DT'] = pd.to_datetime(df['FECHA'], errors='coerce', dayfirst=True) 
            nulos = df['FECHA_DT'].isna().sum()
            validos = df['FECHA_DT'].notna().sum()
            print(f"   Fechas válidas: {validos} | Fechas inválidas (NaT): {nulos}")
            if validos > 0:
                print(f"   Ejemplo válida: {df.loc[df['FECHA_DT'].notna(), 'FECHA'].iloc[0]} -> {df.loc[df['FECHA_DT'].notna(), 'FECHA_DT'].iloc[0]}")
            if nulos > 0:
                # Muestra la primera fecha que no se pudo parsear para ayudar al debug
                print(f"   Ejemplo inválida: {df.loc[df['FECHA_DT'].isna(), 'FECHA'].iloc[0]}") 
        
except Exception as e:
    print(f"❌ Error procesando datos: {e}")

print("\n" + "="*50)
print("FIN DEL DIAGNÓSTICO")