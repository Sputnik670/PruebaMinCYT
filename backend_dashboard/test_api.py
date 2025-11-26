import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

print(f"🔑 Probando llave: {api_key[:5]}... (Longitud: {len(api_key)})")
print("\n📋 Consultando lista de modelos disponibles para tu API Key...")

try:
    found = False
    for m in genai.list_models():
        # Filtramos solo los que sirven para chatear (generateContent)
        if 'generateContent' in m.supported_generation_methods:
            print(f"   ✅ Disponible: {m.name}")
            if 'flash' in m.name:
                found = True
    
    if not found:
        print("\n⚠️ ADVERTENCIA: No veo ningún modelo 'flash' en tu lista.")
        print("Posible solución: Crea una API Key nueva en https://aistudio.google.com/")
    else:
        print("\n🎉 ¡Encontrado! Usa uno de los nombres de arriba en tu código.")

except Exception as e:
    print(f"\n❌ Error crítico al listar modelos: {e}")