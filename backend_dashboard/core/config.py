import os
from dotenv import load_dotenv

# Carga las variables del archivo .env
load_dotenv()

class Settings:
    # Lee las variables de entorno
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    MODEL_NAME = os.getenv("MODEL_NAME", "google/gemini-flash-1.5")
    
    # Validación de seguridad: Si no hay clave, avisar inmediatamente
    if not OPENROUTER_API_KEY:
        # Esto imprimirá un error en la consola si falta la clave
        print("⚠️ ADVERTENCIA: No se encontró OPENROUTER_API_KEY en las variables de entorno.")

# Instanciamos la clase para poder importarla en otros lados
settings = Settings()