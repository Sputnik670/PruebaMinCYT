import sys
import os
import pandas as pd
import logging

# Configuración básica para que Python encuentre tus módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# --- IMPORTAMOS TU LÓGICA REAL ---
try:
    from tools.dashboard import procesar_fila_cliente
    print("✅ Módulo tools.dashboard importado correctamente.")
except ImportError as e:
    print(f"❌ Error importando dashboard: {e}")
    exit()

# Definimos la función de limpieza idéntica a la que pusiste en analysis.py
# (La copiamos aquí para aislar la prueba de la conexión a internet de LangChain)
def limpiar_moneda_test(valor):
    if not valor: return 0.0
    val_str = str(valor).strip()
    # Eliminar símbolos comunes
    val_str = val_str.replace('$', '').replace('USD', '').replace('€', '').strip()
    
    # Lógica inteligente para puntos y comas
    if ',' in val_str and '.' in val_str:
        # Formato 1.000,50 -> 1000.50
        val_str = val_str.replace('.', '').replace(',', '.')
    elif ',' in val_str:
        # Formato 500,50 -> 500.50
        val_str = val_str.replace(',', '.')
    
    # Dejar solo números y el punto decimal
    val_str = ''.join(c for c in val_str if c.isdigit() or c == '.')
    
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def ejecutar_prueba():
    print("\n--- 1. SIMULANDO DATOS DE GOOGLE SHEETS ---")
    # Estos son casos difíciles que solían fallar (nombres de columna distintos, formatos raros)
    datos_mock = [
        {"Fecha": "01/11", "Evento": "Viaje A", "Costo del Traslado": "$ 10.000,00", "Lugar": "CABA"}, # Formato estándar
        {"Fecha": "02/11", "Evento": "Viaje B", "Precio": "5000", "Destino": "Córdoba"},               # Columna "Precio" (tu lógica nueva debe detectarla)
        {"Fecha": "03/11", "Evento": "Viaje C", "Valor": "1.500,50", "Lugar": "Rosario"},              # Columna "Valor" y decimales con coma
        {"Fecha": "04/11", "Evento": "Viaje D", "Monto": "USD 200.00", "Lugar": "Exterior"},           # Moneda extranjera
        {"Fecha": "05/11", "Evento": "Viaje E", "Costo": "", "Lugar": "Mendoza"},                      # Vacío
    ]
    
    print(f"Casos de prueba: {len(datos_mock)} filas.")

    print("\n--- 2. PROBANDO TU LÓGICA DE CAPTURA (dashboard.py) ---")
    filas_procesadas = []
    for i, fila in enumerate(datos_mock):
        # Esta función usa tu código nuevo para buscar "costo", "precio", "valor", etc.
        res = procesar_fila_cliente(fila)
        filas_procesadas.append(res)
        
        raw_costo = res.get('COSTO', 'NO ENCONTRADO')
        print(f"Fila {i+1}: Columna detectada -> '{raw_costo}'")

    print("\n--- 3. PROBANDO LIMPIEZA MATEMÁTICA (analysis.py logic) ---")
    df = pd.DataFrame(filas_procesadas)
    
    # Aplicamos la limpieza
    df['COSTO_NUMERICO'] = df['COSTO'].apply(limpiar_moneda_test)
    
    # Mostramos la tabla resultante
    print(df[['MOTIVO / EVENTO', 'COSTO', 'COSTO_NUMERICO']].to_string())
    
    total_calculado = df['COSTO_NUMERICO'].sum()
    
    # El total debería ser: 10000 + 5000 + 1500.5 + 200 + 0 = 16700.5
    total_esperado = 16700.5
    
    print(f"\n💰 SUMA TOTAL OBTENIDA: {total_calculado}")
    print(f"🎯 SUMA ESPERADA:      {total_esperado}")
    
    if abs(total_calculado - total_esperado) < 0.1:
        print("\n✅ PRUEBA EXITOSA: Tu lógica funciona perfectamente.")
    else:
        print("\n❌ PRUEBA FALLIDA: Los números no coinciden. Revisa la lógica de limpieza.")

if __name__ == "__main__":
    ejecutar_prueba()