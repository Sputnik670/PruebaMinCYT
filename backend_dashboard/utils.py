# backend_dashboard/utils.py
import re

def limpiar_monto_hibrido(texto):
    if not texto: return 0.0
    texto_limpio = re.sub(r'(?i)[a-z$u]+', '', str(texto)).strip()
    
    # Lógica para detectar formato USA (2,363.60) vs ARG
    if ',' in texto_limpio and '.' in texto_limpio:
        if texto_limpio.find(',') < texto_limpio.find('.'):
            # Formato USA: borrar coma de miles
            texto_limpio = texto_limpio.replace(',', '') 
        else:
            # Formato ARG: borrar punto de miles, coma a punto
            texto_limpio = texto_limpio.replace('.', '').replace(',', '.')
            
    try:
        return float(texto_limpio)
    except ValueError:
        return 0.0