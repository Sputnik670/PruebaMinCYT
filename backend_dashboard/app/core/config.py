from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Dashboard Interno Google"
    GOOGLE_CREDENTIALS_FILE: str = "service_account.json"
    # ID de la hoja de cálculo (lo sacas de la URL de tu Google Sheet)
    SPREADSHEET_ID: str 

    class Config:
        env_file = ".env"

settings = Settings()
