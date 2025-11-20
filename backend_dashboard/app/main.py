import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Configuración de CORS
# Permitimos orígenes locales y de producción (Vercel/Render/Dominio propio)
origins = [
    "http://localhost:5173", 
    "http://127.0.0.1:5173",
    "https://pruebaminicyt.onrender.com",
    "https://pruebasmincyt.ar",
    "https://www.pruebasmincyt.ar",
    "https://pruebamincyt-git-main-sputnik670s-projects.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"],
)

# --- TUS ENLACES DE GOOGLE SHEETS (Insertados) ---

# 1. BITÁCORA (Datos de Calendar/Tiempo - Hoja Bitácora)
URL_BITACORA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv"

# 2. VENTAS/PROYECTOS (Datos de Inversión - Hoja Proyectos)
# Nota: Usamos esta URL para el gráfico de Inversión y la tabla de proyectos.
URL_VENTAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv"

# 3. DATOS EXTRA (Nuevo archivo CSV agregado)
URL_DATOS_EXTRA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiN48tufdUP4BDXv7cVrh80OI8Li2KqjXQ-4LalIFCJ9ZnMYHr3R4PvSrPDUsk_g/pub?output=csv"

def leer_google_sheet(url):
    """Función reutilizable para leer cualquier sheet como tabla cruda."""
    try:
        # Lee la primera fila como cabecera.
        df = pd.read_csv(url, header=0) 
        df = df.fillna("")
        return df.to_dict(orient="records")
    except Exception as e:
        return {"error": str(e)}


@app.get("/")
def read_root():
    """Ruta raíz para verificar que la API está activa."""
    return {"mensaje": "API Activa"}


@app.get("/api/metricas")
def obtener_metricas():
    """Obtiene los datos de la Bitácora (Tiempo)."""
    return leer_google_sheet(URL_BITACORA)


@app.get("/api/datosextra")
def obtener_datos_extra_crudos():
    """Obtiene los datos crudos del nuevo archivo CSV."""
    return leer_google_sheet(URL_DATOS_EXTRA)


@app.get("/api/proyectos_crudas")
def obtener_proyectos_crudas():
    """Obtiene los datos crudos de la hoja Proyectos (usando URL_VENTAS)."""
    return leer_google_sheet(URL_VENTAS)


@app.get("/api/ventas_crudas") # Alias por compatibilidad
def obtener_ventas_crudas_alias():
     return leer_google_sheet(URL_VENTAS)


@app.get("/api/tendencia_inversion")
def obtener_tendencia_inversion():
    """Procesa la tendencia de inversión por mes (adaptado a la hoja Proyectos)."""
    try:
        # Lee la hoja Proyectos usando URL_VENTAS
        df = pd.read_csv(URL_VENTAS, header=0) 
        
        # 1. RENOMBRAR COLUMNAS
        # Mapea 'Inversión' y 'FechaInicio' a nombres estándar para el análisis
        # Si en el futuro cambias los nombres en el Sheet, ajústalos aquí.
        df.rename(columns={'Inversión': 'Venta', 'FechaInicio': 'Fecha'}, inplace=True)
        
        # 2. CONVERSIÓN DE FECHA (formato DD/MM/YYYY)
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