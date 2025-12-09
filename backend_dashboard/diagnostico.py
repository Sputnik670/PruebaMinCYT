import os
import logging
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

# Cargar entorno
load_dotenv()

# Configurar logs
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("Diagnostico")

print("\n" + "="*50)
print("🩺 INICIANDO DIAGNÓSTICO DEL SISTEMA (NUEVA ARQUITECTURA)")
print("="*50 + "\n")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("❌ ERROR CRÍTICO: Faltan las credenciales SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en .env")
    exit()

supabase = create_client(url, key)

# --- 1. PRUEBA DE CONEXIÓN Y MEMORIA (Chat) ---
print("👉 1. VERIFICANDO SISTEMA DE CHAT (Lectura/Escritura)...")

try:
    # Intentamos leer la tabla de sesiones (si existe)
    res = supabase.table("sesiones_chat").select("count", count="exact").limit(1).execute()
    count = res.count if res.count is not None else 0
    print(f"   ✅ Conexión Exitosa. Sesiones de chat almacenadas: {count}")
except Exception as e:
    print(f"   ⚠️ Alerta: No se pudo leer 'sesiones_chat'. ¿Ya corriste las migraciones SQL? Error: {e}")

# --- 2. PRUEBA DE DATOS DE AGENDA (Sync) ---
print("\n👉 2. VERIFICANDO DATOS DE AGENDA (Sincronizados)...")

try:
    # Consultamos la tabla definitiva
    response = supabase.table("agenda_unificada").select("*").limit(5).execute()
    datos = response.data

    if not datos:
        print("   ⚠️ La tabla 'agenda_unificada' está VACÍA.")
        print("   💡 SOLUCIÓN: Ejecuta el script de sincronización manualmente una vez:")
        print("      python -m services.sync_sheets")
    else:
        print(f"   ✅ Se encontraron datos. Mostrando muestra de {len(datos)} registros:")
        
        df = pd.DataFrame(datos)
        # Seleccionamos columnas clave para mostrar
        cols = ['fecha', 'titulo', 'funcionario', 'costo', 'moneda']
        # Filtramos solo las que existan en el DF
        cols_final = [c for c in cols if c in df.columns]
        
        print("\n" + df[cols_final].to_string(index=False))
        
        # Validación de Moneda
        if 'moneda' in df.columns:
            monedas = df['moneda'].unique()
            print(f"\n   💰 Monedas detectadas en esta muestra: {monedas}")
        
except Exception as e:
    print(f"\n❌ ERROR CRÍTICO LEYENDO AGENDA: {e}")
    print("   Verifica que la tabla 'agenda_unificada' exista en Supabase.")

print("\n" + "="*50)
print("FIN DEL DIAGNÓSTICO")