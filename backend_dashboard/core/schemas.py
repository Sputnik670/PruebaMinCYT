from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import date, datetime
import re

class AgendaBase(BaseModel):
    fecha: date
    titulo: str
    lugar: str
    ambito: str = "No especificado"

    @field_validator('fecha', mode='before')
    @classmethod
    def parsear_fecha_flexible(cls, v: str | date | datetime) -> date:
        if isinstance(v, (date, datetime)):
            return v.date() if isinstance(v, datetime) else v
        if isinstance(v, str):
            # Busca patrones DD/MM/AAAA o DD/MM
            match = re.search(r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?', v)
            if match:
                d, m, y = match.groups()
                year = int(y) if y else 2025 # Año por defecto si falta
                return date(year, int(m), int(d))
        raise ValueError(f"Fecha inválida: {v}")

class ViajeGestion(AgendaBase):
    funcionario: str
    # NUEVO: Campos unificados
    costo: float = 0.0
    moneda: str = "ARS"
    
    # Campo auxiliar para recibir el string crudo del Excel (ej: "USD 1.500")
    costo_raw: Optional[str | float | int] = Field(default=None, exclude=True)
    
    num_expediente: Optional[str] = None
    estado: str = "Pendiente"

    @model_validator(mode='before')
    @classmethod
    def procesar_dinero(cls, data: any) -> any:
        """
        Detecta moneda y limpia el monto desde 'costo_raw' o inputs directos.
        """
        if isinstance(data, dict):
            # Mapeamos la entrada del Excel (costo_raw) a nuestros campos
            raw = data.get('costo_raw') or data.get('costo')
            
            if not raw:
                data['costo'] = 0.0
                data['moneda'] = 'ARS'
                return data

            s = str(raw).upper().strip()
            
            # 1. Detección de Moneda
            moneda = 'ARS'
            if 'USD' in s or 'DOLAR' in s or 'U$S' in s: moneda = 'USD'
            elif 'EUR' in s or 'EURO' in s or '€' in s: moneda = 'EUR'
            
            # 2. Limpieza de Número
            limpio = re.sub(r'[^\d.,-]', '', s)
            if ',' in limpio and '.' in limpio:
                 limpio = limpio.replace('.', '').replace(',', '.')
            elif ',' in limpio:
                 limpio = limpio.replace(',', '.')
            
            try:
                monto = float(limpio)
            except ValueError:
                monto = 0.0
                
            data['costo'] = monto
            data['moneda'] = moneda
            
        return data

class EventoOficial(AgendaBase):
    organizador: Optional[str] = None
    participantes: Optional[str] = None