import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import numpy as np

app = FastAPI()

# --- CONFIGURACIÓN DE CORS ---
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
# Nota: Asegúrate de que estos GID son correctos y las hojas son públicas
URL_BITACORA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv"
URL_VENTAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv"
URL_DATOS_EXTRA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=1611579313&single=true&output=csv"

# --- FUNCIONES AUXILIARES ---

def limpiar_moneda(valor):
    """
    Recibe un valor (string o numero), quita signos $ y ,
    y devuelve un float. Si falla, devuelve 0.0
    """
    if pd.isna(valor) or valor == "":
        return 0.0
    
    str_val = str(valor)
    # Quitar símbolo de moneda y espacios
    str_val = str_val.replace("$", "").replace(" ", "").strip()
    
    # Manejo de miles y decimales:
    # Asumimos formato latino: 1.000,00 (punto miles, coma decimal)
    # O formato simple: 1000
    try:
        if "," in str_val and "." in str_val:
            # Caso complejo: 1.500,50 -> quitamos puntos, cambiamos coma por punto
            str_val = str_val.replace(".", "").replace(",", ".")
        elif "," in str_val:
             # Caso solo coma: 1500,50 -> cambiamos coma por punto
            str_val = str_val.replace(",", ".")
        
        return float(str_val)
    except ValueError:
        return 0.0

def leer_google_sheet(url):
    try:
        # header=0 implica que la fila 1 son los títulos
        df = pd.read_csv(url, header=0)
        df = df.fillna("") # Rellenar vacíos para que JSON no se rompa
        return df.to_dict(orient="records")
    except Exception as e:
        # Lanzar un error 500 real para que el frontend sepa que falló
        print(f"Error leyendo sheet: {e}")
        raise HTTPException(status_code=500, detail=f"Error leyendo Google Sheet: {str(e)}")

# --- RUTAS ---

@app.get("/")
def read_root():
    return {"mensaje": "API Activa v4 - Auditoría Completada"}

@app.get("/api/metricas")
def obtener_metricas():
    return leer_google_sheet(URL_BITACORA)

@app.get("/api/datosextra")
def obtener_datos_extra_crudos():
    return leer_google_sheet(URL_DATOS_EXTRA)

# Unificamos las rutas de ventas/proyectos si traen lo mismo
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
        
        # 1. Normalización de nombres
        if 'Inversión' in df.columns:
            df.rename(columns={'Inversión': 'Venta', 'FechaInicio': 'Fecha'}, inplace=True)
        elif 'Inversion' in df.columns:
             df.rename(columns={'Inversion': 'Venta', 'FechaInicio': 'Fecha'}, inplace=True)
        
        # Validación: Si no existen las columnas tras renombrar, error
        if 'Fecha' not in df.columns or 'Venta' not in df.columns:
             raise HTTPException(status_code=500, detail="Las columnas 'FechaInicio' o 'Inversión' no se encuentran en el CSV.")

        # 2. Limpieza CRÍTICA de Números (La parte que faltaba)
        # Aplicamos la función de limpieza a toda la columna de Venta
        df['Venta'] = df['Venta'].apply(limpiar_moneda)

        # 3. Procesamiento de Fechas
        # dayfirst=True ayuda a pandas a entender formatos latinos (dd/mm/yyyy) mejor
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
        df.dropna(subset=['Fecha'], inplace=True)
        
        # 4. Agrupación
        # Agrupamos por mes y sumamos
        tendencia = df.groupby(df['Fecha'].dt.to_period('M'))['Venta'].sum().reset_index()
        
        # 5. Formato de salida
        # Convertimos el periodo a string 'YYYY-MM' para que el gráfico lo entienda
        tendencia['Fecha'] = tendencia['Fecha'].astype(str)
        
        # Ordenar por fecha para que el gráfico no salga revuelto
        tendencia = tendencia.sort_values('Fecha')

        return tendencia.to_dict(orient="records")

    except Exception as e:
        print(f"Error procesando tendencia: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando datos: {str(e)}")