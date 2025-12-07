import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(url, key)

def verificar():
    print("\n🕵️  VERIFICANDO DATOS EN SUPABASE...")
    
    # Traemos los últimos 10 registros ingresados
    response = supabase.table("agenda_unificada")\
        .select("titulo, costo, moneda, origen_dato")\
        .order("id", desc=True)\
        .limit(10)\
        .execute()
    
    datos = response.data
    
    print(f"\n📝 Últimos {len(datos)} registros encontrados:\n")
    print(f"{'MONEDA':<10} | {'COSTO':<15} | {'TÍTULO'}")
    print("-" * 60)
    
    for fila in datos:
        m = fila.get('moneda', '---')
        c = fila.get('costo', 0)
        t = fila.get('titulo', 'Sin título')[:30] # Cortamos títulos largos
        
        # Alerta visual si vemos el error antiguo
        estado = "✅"
        if m == "ARS" and c == 0:
            estado = "⚠️ (Posible error)"
            
        print(f"{m:<10} | {c:<15} | {t} {estado}")

if __name__ == "__main__":
    verificar()