import os
import google.generativeai as genai
from dotenv import load_dotenv

# Cargar entorno
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ ERROR: No se encontró la GOOGLE_API_KEY en el archivo .env")
else:
    print(f"🔑 Clave detectada: {api_key[:5]}... (Longitud: {len(api_key)})")
    genai.configure(api_key=api_key)

    print("\n📡 Consultando modelos disponibles a Google...")
    
    try:
        hay_flash = False
        print(f"{'NOMBRE DEL MODELO':<30} | {'MÉTODOS SOPORTADOS'}")
        print("-" * 60)
        
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"{m.name:<30} | {m.supported_generation_methods}")
                if 'flash' in m.name:
                    hay_flash = True
        
        print("-" * 60)
        
        if hay_flash:
            print("\n✅ ¡BUENAS NOTICIAS! Tienes acceso a modelos Flash.")
            print("👉 Busca en la lista de arriba el nombre EXACTO (ej: 'models/gemini-1.5-flash-001').")
            print("   Ese es el nombre que debemos poner en el código.")
        else:
            print("\n⚠️ NO veo modelos Flash. Probablemente debamos usar 'models/gemini-pro'.")

    except Exception as e:
        print(f"\n❌ Error de conexión: {e}")