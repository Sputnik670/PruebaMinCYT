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

# --- TUS ENLACES DE GOOGLE SHEETS ---
# NOTA: Asegúrate de que URL_PROYECTOS apunte al enlace CSV de tu hoja "Proyectos"
# Utiliza la URL de la hoja Proyectos para ambas variables si solo tienes esa hoja.
URL_BITACORA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv" 
URL_VENTAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv" 

def leer_google_sheet(url):
    """Función reutilizable para leer cualquier sheet como tabla cruda."""
    try:
        # Lee la primera fila como cabecera.
        df = pd.read_csv(url, header=0) 
        df = df.fillna("")
        return df.to_dict(orient="records")
    except Exception as e:
        # Devuelve un error si el URL está mal o el archivo no existe.
        return {"error": str(e)}


@app.get("/")
def read_root():
    """Ruta raíz para verificar que la API está activa."""
    return {"mensaje": "API Activa"}


@app.get("/api/metricas")
def obtener_metricas():
    """Obtiene los datos de la Bitácora (Tiempo)."""
    return leer_google_sheet(URL_BITACORA)


@app.get("/api/proyectos_crudas")
def obtener_proyectos_crudas():
    """Obtiene los datos crudos de la hoja Proyectos/Inversión."""
    return leer_google_sheet(URL_PROYECTOS)


@app.get("/api/tendencia_inversion") # RUTA FINAL ADAPTADA
def obtener_tendencia_inversion():
    """Procesa la tendencia de inversión por mes (adaptado a Proyectos)."""
    try:
        # Lee la hoja Proyectos
        df = pd.read_csv(URL_PROYECTOS, header=0) 
        
        # 1. RENOMBRAR COLUMNAS PARA EL ANÁLISIS
        # CRÍTICO: Usamos 'Inversión' y 'FechaInicio'
        # Renombra 'Inversión' a 'Venta' (para que el código de Pandas lo procese)
        # y 'FechaInicio' a 'Fecha'
        df.rename(columns={'Inversión': 'Venta', 'FechaInicio': 'Fecha'}, inplace=True)
        
        # 2. CONVERSIÓN DE FECHA
        # Asume formato Día/Mes/Año (DD/MM/YYYY)
        df['Fecha'] = pd.to_datetime(df['Fecha'], format='%d/%m/%Y', errors='coerce')
        
        # Eliminar filas sin fecha válida
        df.dropna(subset=['Fecha'], inplace=True)
        
        # 3. SUMA POR MES/AÑO
        tendencia = df.groupby(df['Fecha'].dt.to_period('M'))['Venta'].sum().reset_index()
        
        # 4. FORMATEO FINAL
        tendencia['Fecha'] = tendencia['Fecha'].astype(str)
        
        return tendencia.to_dict(orient="records")
    except Exception as e:
        return {"error": f"Error procesando Proyectos: {str(e)}"}