import os
import sys
import logging
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importamos ambas funciones legacy
from tools.legacy_sheets import get_data_cliente_legacy, get_data_ministerio_legacy
from core.schemas import ViajeGestion, EventoOficial

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("MIGRACION")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(url, key)

def migrar_todo():
    print("\n🔥 INICIANDO MIGRACIÓN CON RANGOS DE FECHA...")
    
    # 1. Limpieza Total
    print("🧹 Borrando todos los datos de 'agenda_unificada'...")
    supabase.table("agenda_unificada").delete().neq("id", 0).execute()

    # --- PARTE A: GESTIÓN INTERNA ---
    print("\n--- MIGRANDO GESTIÓN INTERNA ---")
    raw_cliente = get_data_cliente_legacy()
    count_cli = 0
    
    for i, fila in enumerate(raw_cliente):
        try:
            obj = ViajeGestion(
                fecha=fila.get("FECHA_VIAJE"),
                titulo=fila.get("MOTIVO_EVENTO") or "Sin título",
                lugar=fila.get("DESTINO") or "Desconocido",
                funcionario=fila.get("FUNCIONARIO") or "No asignado",
                costo_raw=fila.get("COSTO_TRASLADO"), # Pydantic detectará moneda aquí
                num_expediente=fila.get("NUMERO_EXPEDIENTE"),
                estado=fila.get("ESTADO_TRAMITE", "Pendiente"),
                ambito="Gestión Interna"
            )
            
            registro = {
                "fecha": obj.fecha.isoformat(),
                # 👇 AQUÍ ESTABA EL FALTANTE: Guardar la fecha de fin calculada
                "fecha_fin": obj.fecha_fin.isoformat() if obj.fecha_fin else None,
                "titulo": obj.titulo,
                "lugar": obj.lugar,
                "ambito": obj.ambito,
                "funcionario": obj.funcionario,
                "costo": obj.costo,
                "moneda": obj.moneda,
                "num_expediente": obj.num_expediente,
                "estado": obj.estado,
                "origen_dato": "MisionesOficiales"
            }
            supabase.table("agenda_unificada").insert(registro).execute()
            count_cli += 1
        except Exception as e:
            print(f"❌ Error Cliente Fila {i}: {e}")

    # --- PARTE B: AGENDA OFICIAL ---
    print("\n--- MIGRANDO AGENDA OFICIAL ---")
    raw_ministerio = get_data_ministerio_legacy()
    count_min = 0

    for i, fila in enumerate(raw_ministerio):
        try:
            obj = EventoOficial(
                fecha=fila.get("FECHA"),
                titulo=fila.get("EVENTO") or "Evento Oficial",
                lugar=fila.get("LUGAR") or "A confirmar",
                ambito=fila.get("AMBITO") or "Oficial",
                organizador=fila.get("ORGANIZADOR"),
                participantes=fila.get("PARTICIPANTE")
            )

            registro = {
                "fecha": obj.fecha.isoformat(),
                # 👇 AQUÍ TAMBIÉN FALTABA
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

    print(f"\n🏁 RESTAURACIÓN FINALIZADA")
    print(f"   Gestión Interna: {count_cli} registros")
    print(f"   Agenda Oficial:  {count_min} registros")

if __name__ == "__main__":
    migrar_todo()