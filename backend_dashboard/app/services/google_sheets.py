import gspread
from app.core.config import settings

class GoogleSheetService:
    def __init__(self):
        # Conectamos usando la Service Account
        try:
            self.gc = gspread.service_account(filename=settings.GOOGLE_CREDENTIALS_FILE)
            self.sh = self.gc.open_by_key(settings.SPREADSHEET_ID)
        except Exception as e:
            print(f"Error fatal conectando a Google: {e}")
            raise e

    def get_data(self, worksheet_name: str = "Hoja 1"):
        """Obtiene todos los registros de una hoja como lista de diccionarios"""
        worksheet = self.sh.worksheet(worksheet_name)
        return worksheet.get_all_records()

    def add_row(self, data: dict, worksheet_name: str = "Hoja 1"):
        """Agrega una fila nueva"""
        worksheet = self.sh.worksheet(worksheet_name)
        # Convierte valores del dict a lista simple (según orden de columnas)
        worksheet.append_row(list(data.values()))
        return {"status": "success", "data": data}

# Instancia global para reutilizar la conexión
sheet_service = GoogleSheetService()