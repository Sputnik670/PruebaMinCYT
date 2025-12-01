from tools.analysis import parse_money_value, get_dataframe_cliente

print("\n--- 1. PROBANDO DETECCIÓN DE MONEDA ---")
casos = [
    ("USD 1,200.50", "USD", 1200.50),
    ("1500 €", "EUR", 1500.0),
    ("$ 50.000,00", "ARS", 50000.0),
    ("EUR 100", "EUR", 100.0)
]

for texto, mon_esp, monto_esp in casos:
    moneda, monto = parse_money_value(texto)
    check = "✅" if (moneda == mon_esp and monto == monto_esp) else "❌"
    print(f"{check} Entrada: '{texto}' -> Detectado: {moneda} {monto}")

print("\n--- 2. PROBANDO DATAFRAME REAL (Si tienes credenciales) ---")
try:
    df = get_dataframe_cliente()
    if not df.empty and 'MONEDA' in df.columns:
        print("✅ Columnas nuevas detectadas:", df.columns.tolist())
        print("\nEjemplo de datos procesados:")
        print(df[['MOTIVO / EVENTO', 'COSTO_ORIGINAL', 'MONEDA', 'MONTO']].head(5).to_string())
        
        # Prueba de suma
        total = df.groupby('MONEDA')['MONTO'].sum()
        print("\n💰 TOTALES CALCULADOS POR PYTHON:")
        print(total)
    else:
        print("⚠️ El DataFrame está vacío o no tiene las columnas nuevas.")
except Exception as e:
    print(f"❌ Error al conectar con Google Sheets: {e}")