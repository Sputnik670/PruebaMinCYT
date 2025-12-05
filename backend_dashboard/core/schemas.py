from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import date, datetime
import re

# Diccionario para entender meses en texto
MESES = {
    'enero': 1, 'ene': 1, 'jan': 1, 'febrero': 2, 'feb': 2, 'marzo': 3, 'mar': 3,
    'abril': 4, 'abr': 4, 'apr': 4, 'mayo': 5, 'may': 5, 'junio': 6, 'jun': 6,
    'julio': 7, 'jul': 7, 'agosto': 8, 'ago': 8, 'aug': 8,
    'septiembre': 9, 'sep': 9, 'set': 9, 'octubre': 10, 'oct': 10,
    'noviembre': 11, 'nov': 11, 'diciembre': 12, 'dic': 12, 'dec': 12
}

class AgendaBase(BaseModel):
    fecha: date = Field(..., description="Fecha de INICIO")
    fecha_fin: Optional[date] = Field(None, description="Fecha de FIN")
    titulo: str
    lugar: str
    ambito: str = "No especificado"

    @model_validator(mode='before')
    @classmethod
    def extraer_rango_fechas(cls, data: any) -> any:
        if isinstance(data, dict):
            # Limpieza inicial: minúsculas y quitar espacios extra
            raw = str(data.get('fecha', '')).lower().strip()
            
            if isinstance(data.get('fecha'), (date, datetime)):
                return data

            year_actual = 2025
            
            # Detectar año explícito (ej: 2026) en el texto
            match_year = re.search(r'(202\d)', raw)
            if match_year:
                year_actual = int(match_year.group(1))

            fechas_encontradas = []

            # --- REGEX PODEROSA PARA RANGOS ---
            # Explicación:
            # 1. (\d{1,2})       -> Primer día (ej: 10)
            # 2. \s+             -> Espacios obligatorios
            # 3. (?:...)         -> Grupo de conectores no capturable
            #    al|a|y|e|-|&|,  -> Acepta "10 al 13", "10 y 13", "10, 13", "10-13"
            # 4. \s+             -> Espacios
            # 5. (\d{1,2})       -> Segundo día (ej: 13)
            
            # ESTRATEGIA 1: Rango con formato numérico "10 y 13/12"
            match_rango_num = re.search(r'(\d{1,2})\s+(?:al|a|y|e|-|&|,)\s+(\d{1,2})[/-](\d{1,2})', raw)
            
            # ESTRATEGIA 2: Rango con formato texto "10 y 13 de diciembre"
            match_rango_txt = re.search(r'(\d{1,2})\s+(?:al|a|y|e|-|&|,)\s+(\d{1,2})\s+(?:de\s+)?([a-z]{3,})', raw)

            if match_rango_num:
                d1, d2, mes = map(int, match_rango_num.groups())
                try:
                    # Interpretamos "10 y 13" como un rango que empieza el 10 y termina el 13
                    fechas_encontradas.append(date(year_actual, mes, d1))
                    fechas_encontradas.append(date(year_actual, mes, d2))
                except: pass

            elif match_rango_txt:
                d1, d2, mes_txt = match_rango_txt.groups()
                mes_num = next((v for k, v in MESES.items() if k in mes_txt), None)
                if mes_num:
                    try:
                        fechas_encontradas.append(date(year_actual, mes_num, int(d1)))
                        fechas_encontradas.append(date(year_actual, mes_num, int(d2)))
                    except: pass

            else:
                # --- ESTRATEGIA 3: FECHAS SUELTAS (Si no es un rango explícito) ---
                # Busca todas las ocurrencias de "DD/MM"
                matches_num = re.findall(r'(\d{1,2})[/-](\d{1,2})', raw)
                for d, m in matches_num:
                    try: fechas_encontradas.append(date(year_actual, int(m), int(d)))
                    except: pass

                # Busca todas las ocurrencias de "DD de mes"
                matches_txt = re.findall(r'(\d{1,2})\s+(?:de\s+)?([a-z]{3,})', raw)
                for d, m_txt in matches_txt:
                    mes_num = next((v for k, v in MESES.items() if k in m_txt), None)
                    if mes_num:
                        try: fechas_encontradas.append(date(year_actual, mes_num, int(d)))
                        except: pass

            # ASIGNACIÓN FINAL
            if fechas_encontradas:
                fechas_encontradas.sort() # Ordenamos cronológicamente
                data['fecha'] = fechas_encontradas[0] # El menor es el inicio
                # Si hay más de una fecha (porque era un rango o había varias), la última es el fin
                data['fecha_fin'] = fechas_encontradas[-1] if len(fechas_encontradas) > 1 else fechas_encontradas[0]

        return data

class ViajeGestion(AgendaBase):
    funcionario: str
    costo: float = 0.0
    moneda: str = "ARS"
    costo_raw: Optional[str | float | int] = Field(default=None, exclude=True)
    num_expediente: Optional[str] = None
    estado: str = "Pendiente"

    @model_validator(mode='before')
    @classmethod
    def procesar_dinero(cls, data: any) -> any:
        if isinstance(data, dict):
            raw = data.get('costo_raw') or data.get('costo')
            if not raw:
                data['costo'] = 0.0
                data['moneda'] = 'ARS'
                return data

            s = str(raw).upper().strip()
            moneda = 'ARS'
            if 'USD' in s or 'DOLAR' in s or 'U$S' in s: moneda = 'USD'
            elif 'EUR' in s or 'EURO' in s or '€' in s: moneda = 'EUR'
            
            limpio = re.sub(r'[^\d.,-]', '', s)
            if ',' in limpio and '.' in limpio: limpio = limpio.replace('.', '').replace(',', '.')
            elif ',' in limpio: limpio = limpio.replace(',', '.')
            
            try: data['costo'] = float(limpio)
            except: data['costo'] = 0.0
            data['moneda'] = moneda
        return data

class EventoOficial(AgendaBase):
    organizador: Optional[str] = None
    participantes: Optional[str] = None