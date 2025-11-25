from langchain.tools import tool
import json

@tool
def crear_borrador_email(destinatario: str, asunto: str, cuerpo: str) -> str:
    """
    Crea un borrador de correo electrónico con los campos: destinatario, asunto y cuerpo.
    Esta herramienta NO ENVÍA el email, solo lo estructura como JSON para que el
    Agente se lo presente al usuario y pida confirmación antes de la acción final.
    """
    # En un entorno real, aquí harías una validación de formato
    
    borrador = {
        "accion_requerida": "Confirmación de envío de email",
        "destinatario": destinatario,
        "asunto": asunto,
        "cuerpo_borrador": cuerpo
    }
    
    # Devolvemos un JSON que el Agente usará para la respuesta final al usuario
    return json.dumps(borrador, indent=2, ensure_ascii=False)