import os
from dotenv import load_dotenv

# Carga las variables del archivo .env (para desarrollo local)
load_dotenv()

class Settings:
    # 1. Claves de API Críticas
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    
    # 2. Credenciales de Google Sheets (Solo verificamos que existan)
    GOOGLE_CLIENT_EMAIL = os.getenv("GOOGLE_CLIENT_EMAIL")
    GOOGLE_PRIVATE_KEY = os.getenv("GOOGLE_PRIVATE_KEY")

    # Validaciones de seguridad al arrancar
    if not GOOGLE_API_KEY:
        print("⚠️ ADVERTENCIA: Falta GOOGLE_API_KEY. El agente de IA no funcionará.")
    
    if not TAVILY_API_KEY:
        print("⚠️ ADVERTENCIA: Falta TAVILY_API_KEY. La búsqueda en internet fallará.")

settings = Settings()