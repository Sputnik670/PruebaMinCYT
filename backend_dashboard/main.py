import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Configuración de CORS
origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- TUS ENLACES (DEBEN APUNTAR A LAS PESTAÑAS ESPECÍFICAS) ---
# https://play.google.com/store/apps/details?id=com.cfia.Bitacora&hl=es_CR
URL_BITACORA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv"

# https://www.youtube.com/watch?v=N0P7-spcB2A
URL_VENTAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv" 

def leer_google_sheet(url):
    """Función reutilizable para leer cualquier sheet"""
    try:
        # header=1 indica que use la SEGUNDA FILA como cabecera (en caso de que la primera siga vacía)
        df = pd.read_csv(url, header=0) 
        df = df.fillna("")
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
def read_root():
    return {"mensaje": "API Activa"}

@app.get("/api/metricas") # RUTA 1: BITÁCORA (Tiempo)
def obtener_metricas():
    return leer_google_sheet(URL_BITACORA)

@app.get("/api/ventas")  # RUTA 2: VENTAS (Dinero)
def obtener_ventas():
    return leer_google_sheet(URL_VENTAS)