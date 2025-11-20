import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# --- CONFIGURACIÓN DE CORS (PERMISOS) ---
# Aquí agregamos Vercel y Render para que no te bloquee
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://prueba-mincyt.onrender.com",
    "https://pruebamincyt.ar",
    "https://www.pruebasmincyt.ar",
    "https://pruebamincyt.vercel.app",
    "https://pruebamincyt-git-main-sputnik670s-projects.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- TUS ENLACES DE GOOGLE SHEETS ---
URL_BITACORA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv"
URL_VENTAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv"
URL_DATOS_EXTRA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"

def leer_google_sheet(url):
    try:
        df = pd.read_csv(url, header=0)
        df = df.fillna("")
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": str(e)}

@app.get("/")
def read_root():
    return {"mensaje": "API Activa v3 - Todo Correcto"}

# --- RUTAS CON PREFIJO /api ---
@app.get("/api/metricas")
def obtener_metricas():
    return leer_google_sheet(URL_BITACORA)

@app.get("/api/datosextra")
def obtener_datos_extra_crudos():
    return leer_google_sheet(URL_DATOS_EXTRA)

@app.get("/api/proyectos_crudas")
def obtener_proyectos_crudas():
    return leer_google_sheet(URL_VENTAS)

@app.get("/api/ventas_crudas")
def obtener_ventas_crudas_alias():
     return leer_google_sheet(URL_VENTAS)

@app.get("/api/tendencia_inversion")
def obtener_tendencia_inversion():
    try:
        df = pd.read_csv(URL_VENTAS, header=0)
        # Normalización de nombres de columna
        if 'Inversión' in df.columns:
            df.rename(columns={'Inversión': 'Venta', 'FechaInicio': 'Fecha'}, inplace=True)
        elif 'Inversion' in df.columns:
             df.rename(columns={'Inversion': 'Venta', 'FechaInicio': 'Fecha'}, inplace=True)

        df['Fecha'] = pd.to_datetime(df['Fecha'], format='%d/%m/%Y', errors='coerce')
        df.dropna(subset=['Fecha'], inplace=True)
        
        tendencia = df.groupby(df['Fecha'].dt.to_period('M'))['Venta'].sum().reset_index()
        tendencia['Fecha'] = tendencia['Fecha'].astype(str)
        return tendencia.to_dict(orient="records")
    except Exception as e:
        return {"error": f"Error procesando Proyectos: {str(e)}"}