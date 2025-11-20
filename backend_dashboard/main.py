import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import io
import requests

app = FastAPI()

# --- 1. PERMISOS (CORS) ---
# Permitimos todo para evitar dolores de cabeza en pruebas.
# En producción estricta podrías limitar esto, pero para tu dashboard está bien.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite a Vercel, Localhost, etc.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. CONFIGURACIÓN ---
# Tus URLs públicas (Ya comprobamos que funcionan)
URL_BITACORA = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=643804140&single=true&output=csv"
URL_VENTAS = "https://docs.google.com/spreadsheets/d/e/2PACX-1vR0-Uk3fi9iIO1XHja2j3nFlcy4NofCDsjzPh69-4D1jJkDUwq7E5qY1S201_e_0ODIk5WksS_ezYHi/pub?gid=0&single=true&output=csv"

# --- 3. HERRAMIENTAS DE LIMPIEZA ---

def limpiar_dinero(valor):
    """Convierte '$ 1.500,00' o '1.500' en el numero float 1500.0"""
    if pd.isna(valor): return 0.0
    s = str(valor).replace("$", "").replace(" ", "").strip()
    # Asumimos formato latino: punto para miles, coma para decimales
    # Si hay coma, reemplazamos puntos por nada y coma por punto
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s) if s else 0.0

def cargar_csv(url):
    """Descarga y lee el CSV de forma segura"""
    try:
        response = requests.get(url)
        response.raise_for_status()
        # Convertimos el texto descargado en un DataFrame
        df = pd.read_csv(io.StringIO(response.text))
        df = df.fillna("") # Rellenamos huecos vacíos
        return df
    except Exception as e:
        print(f"Error cargando CSV: {e}")
        return None

# --- 4. RUTAS (ENDPOINTS) ---

@app.get("/")
def home():
    return {"status": "online", "mensaje": "Backend funcionando correctamente 🚀"}

@app.get("/api/dashboard")
def get_dashboard_data():
    """
    Esta es la RUTA MAESTRA.
    Devuelve todo lo que el frontend necesita en una sola llamada.
    """
    # 1. Cargar Bitácora
    df_bitacora = cargar_csv(URL_BITACORA)
    datos_bitacora = df_bitacora.to_dict(orient="records") if df_bitacora is not None else []

    # 2. Cargar y Procesar Ventas (Aquí ocurre la magia de la limpieza)
    df_ventas = cargar_csv(URL_VENTAS)
    datos_tendencia = []
    datos_ventas_crudos = []

    if df_ventas is not None:
        # Guardamos copia cruda para la tabla
        datos_ventas_crudos = df_ventas.to_dict(orient="records")

        # Procesamos para el gráfico (Limpieza)
        # Buscamos la columna de dinero (sea 'Inversión' o 'Inversion' o 'Venta')
        col_dinero = next((c for c in df_ventas.columns if "Invers" in c or "Venta" in c), None)
        col_fecha = next((c for c in df_ventas.columns if "Fecha" in c), None)

        if col_dinero and col_fecha:
            # Limpiamos dinero
            df_ventas['MontoLimpio'] = df_ventas[col_dinero].apply(limpiar_dinero)
            
            # Limpiamos fecha
            df_ventas['FechaDt'] = pd.to_datetime(df_ventas[col_fecha], dayfirst=True, errors='coerce')
            df_ventas.dropna(subset=['FechaDt'], inplace=True)

            # Agrupamos por Mes
            agrupado = df_ventas.groupby(df_ventas['FechaDt'].dt.to_period('M'))['MontoLimpio'].sum().reset_index()
            agrupado['FechaStr'] = agrupado['FechaDt'].astype(str) # '2024-10'

            # Formateamos para JSON
            datos_tendencia = agrupado[['FechaStr', 'MontoLimpio']].rename(
                columns={'FechaStr': 'fecha', 'MontoLimpio': 'monto'}
            ).to_dict(orient="records")

    return {
        "bitacora": datos_bitacora,
        "ventas_tabla": datos_ventas_crudos,
        "tendencia_grafico": datos_tendencia
    }