import os
import sys
import logging
import re
from dotenv import load_dotenv
from supabase import create_client

# Cargar variables de entorno y paths
load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from tools.legacy_sheets import get_data_cliente_legacy, get_data_ministerio_legacy
from core.schemas import ViajeGestion, EventoOficial
from utils import limpiar_monto_hibrido

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("MIGRACION")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(url, key)

def separar_moneda_y_monto(texto_celda):
    """
    Toma un texto como 'USD 2,363.60' y devuelve ('USD', 2363.60).
    """
    if not texto_celda:
        return "ARS", 0.0
    
    texto = str(texto_celda).strip().upper()
    
    # 1. Detectar Moneda
    moneda = "ARS" # Default
    if "USD" in texto or "DOLAR" in texto:
        moneda = "USD"
    elif "EUR" in texto or "EURO" in texto:
        moneda = "EUR"
        
    # 2. Usar tu función utils.py para limpiar el numero correctamente
    # (Tu función ya sabe borrar letras y arreglar comas/puntos)
    costo = limpiar_monto_hibrido(texto)
    
    return moneda, costo

def obtener_valor_flexible(fila, posibles_nombres):
    """Busca una columna probando varios nombres posibles (ignorando mayúsculas)"""
    claves_fila = {k.lower(): k for k in fila.keys()} # Mapa minúscula -> llave real
    
    for nombre in posibles_nombres:
        nombre_lower = nombre.lower()
        if nombre_lower in claves_fila:
            val = fila[claves_fila[nombre_lower]]
            if val: return val
    return None

def migrar_todo():
    print("\n🔥 INICIANDO MIGRACIÓN (MODO FORENSE)...")
    
    # 1. Limpieza
    print("🧹 Borrando agenda_unificada...")
    supabase.table("agenda_unificada").delete().neq("id", 0).execute()

    # --- PARTE A: GESTIÓN INTERNA ---
    print("\n--- MIGRANDO GESTIÓN INTERNA ---")
    raw_cliente = get_data_cliente_legacy()
    count_cli = 0
    
    # DEBUG: Imprimir las columnas reales que lee Python para que veas cómo se llaman
    if raw_cliente:
        print(f"🔎 COLUMNAS DETECTADAS: {list(raw_cliente[0].keys())}")

    for i, fila in enumerate(raw_cliente):
        try:
            # A. Extracción MANUAL de Costo y Moneda
            raw_costo = obtener_valor_flexible(fila, ["costo del traslado", "COSTO_TRASLADO", "Costo", "Importe"])
            moneda_final, costo_final = separar_moneda_y_monto(raw_costo)

            # B. Creación del Objeto (Pydantic)
            obj = ViajeGestion(
                fecha=obtener_valor_flexible(fila, ["FECHA_VIAJE", "Fecha"]),
                titulo=obtener_valor_flexible(fila, ["MOTIVO_EVENTO", "Motivo"]) or "Sin título",
                lugar=obtener_valor_flexible(fila, ["DESTINO", "Lugar"]) or "Desconocido",
                funcionario=obtener_valor_flexible(fila, ["FUNCIONARIO", "Funcionario"]) or "No asignado",
                costo_raw=costo_final, # Le pasamos el float limpio directo
                num_expediente=obtener_valor_flexible(fila, ["NUMERO_EXPEDIENTE", "Expediente"]),
                estado=obtener_valor_flexible(fila, ["ESTADO_TRAMITE", "Estado"]) or "Pendiente",
                ambito="Gestión Interna"
            )
            
            # C. Inyección forzada de los datos correctos
            # (Sobrescribimos lo que sea que Pydantic haya decidido)
            registro = {
                "fecha": obj.fecha.isoformat(),
                "fecha_fin": obj.fecha_fin.isoformat() if obj.fecha_fin else None,
                "titulo": obj.titulo,
                "lugar": obj.lugar,
                "ambito": obj.ambito,
                "funcionario": obj.funcionario,
                
                # DATOS CLAVE ARREGLADOS:
                "costo": costo_final,   # Usamos el valor limpiado por nosotros
                "moneda": moneda_final, # Usamos la moneda detectada por nosotros
                
                "num_expediente": obj.num_expediente,
                "estado": obj.estado,
                "origen_dato": "MisionesOficiales"
            }
            
            supabase.table("agenda_unificada").insert(registro).execute()
            count_cli += 1
            
            # Print de control cada 5 filas para que veas si funciona
            if i < 5: 
                print(f"   ✅ Fila {i}: {raw_costo} -> Detectado: {moneda_final} {costo_final}")

        except Exception as e:
            print(f"❌ Error Cliente Fila {i}: {e}")

    # --- PARTE B: AGENDA OFICIAL (Sin cambios mayores) ---
    print("\n--- MIGRANDO AGENDA OFICIAL ---")
    raw_ministerio = get_data_ministerio_legacy()
    count_min = 0

    for i, fila in enumerate(raw_ministerio):
        try:
            # Usamos el helper flexible también aquí por seguridad
            fecha = obtener_valor_flexible(fila, ["FECHA", "Fecha"])
            titulo = obtener_valor_flexible(fila, ["EVENTO", "Evento"])
            lugar = obtener_valor_flexible(fila, ["LUGAR", "Lugar"])
            
            obj = EventoOficial(
                fecha=fecha,
                titulo=titulo or "Evento Oficial",
                lugar=lugar or "A confirmar",
                ambito=obtener_valor_flexible(fila, ["AMBITO", "Ambito"]) or "Oficial",
                organizador=obtener_valor_flexible(fila, ["ORGANIZADOR", "Organizador"]),
                participantes=obtener_valor_flexible(fila, ["PARTICIPANTE", "Participantes"])
            )

            registro = {
                "fecha": obj.fecha.isoformat(),
                "fecha_fin": obj.fecha_fin.isoformat() if obj.fecha_fin else None,
                "titulo": obj.titulo,
                "lugar": obj.lugar,
                "ambito": obj.ambito,
                "organizador": obj.organizador,
                "participantes": obj.participantes,
                "origen_dato": "CalendarioPublico"
            }
            supabase.table("agenda_unificada").insert(registro).execute()
            count_min += 1
        except Exception as e:
            pass

    print(f"\n🏁 FIN. Registros: {count_cli} Gestión | {count_min} Oficial")

if __name__ == "__main__":
    migrar_todo()