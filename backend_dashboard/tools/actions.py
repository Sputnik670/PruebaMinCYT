import os
import smtplib
import logging
import pandas as pd
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from langchain.tools import tool
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN CALENDAR ---
SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    """Autentica con Google Calendar usando las mismas credenciales que Sheets."""
    try:
        private_key = os.getenv("GOOGLE_PRIVATE_KEY")
        client_email = os.getenv("GOOGLE_CLIENT_EMAIL")
        
        if not private_key or not client_email:
            return None

        creds_dict = {
            "type": "service_account",
            "project_id": "dashboard-impacto-478615",
            "private_key_id": "indefinido",
            "private_key": private_key.replace("\\n", "\n"),
            "client_email": client_email,
            "client_id": "116197238257458301101",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        logger.error(f"Error Auth Calendar: {e}")
        return None

# --- HERRAMIENTAS DE ACCIÓN ---

@tool
def agendar_reunion_oficial(titulo: str, fecha_hora_inicio: str, duracion_minutos: int = 60, emails_invitados: str = ""):
    """
    Agenda una reunión REAL en el Google Calendar del Ministerio.
    
    ARGS:
    - titulo: Asunto de la reunión.
    - fecha_hora_inicio: Formato ISO o 'YYYY-MM-DD HH:MM' (ej: '2023-11-20 15:00').
    - duracion_minutos: Duración en minutos (default 60).
    - emails_invitados: Lista de emails separados por coma (opcional).
    """
    service = get_calendar_service()
    if not service:
        return "Error: No tengo credenciales válidas para escribir en el Calendario."

    try:
        # 1. Parsear fechas
        dt_inicio = pd.to_datetime(fecha_hora_inicio)
        if pd.isna(dt_inicio): dt_inicio = datetime.now() + timedelta(days=1)
        
        dt_fin = dt_inicio + timedelta(minutes=duracion_minutos)

        # 2. Construir descripción con invitados (Workaround para error 403)
        descripcion = 'Reunión agendada automáticamente por Pitu (Asistente Virtual).'
        if emails_invitados:
            descripcion += f"\n\nInvitados propuestos: {emails_invitados}"

        # 3. Construir evento
        event = {
            'summary': f"[IA] {titulo}",
            'description': descripcion,
            'start': {'dateTime': dt_inicio.isoformat(), 'timeZone': 'America/Argentina/Buenos_Aires'},
            'end': {'dateTime': dt_fin.isoformat(), 'timeZone': 'America/Argentina/Buenos_Aires'},
        }

        # --- CORRECCIÓN ERROR 403 ---
        # Comentamos la invitación formal para evitar "Service accounts cannot invite attendees"
        # if emails_invitados:
        #    attendees = [{'email': email.strip()} for email in emails_invitados.split(',') if '@' in email]
        #    if attendees: event['attendees'] = attendees
        # ----------------------------

        # 4. Insertar en el calendario objetivo
        calendar_id = os.getenv("CALENDAR_ID_TARGET", "primary") 
        
        created_event = service.events().insert(calendarId=calendar_id, body=event).execute()
        
        return f"✅ Reunión agendada con éxito: {created_event.get('htmlLink')}"

    except Exception as e:
        logger.error(f"Error creando evento: {e}")
        return f"Fallo al agendar: {str(e)}"

@tool
def enviar_email_real(destinatario: str, asunto: str, cuerpo: str):
    """
    ENVÍA un correo electrónico real vía SMTP. Úsalo solo cuando el usuario confirme explícitamente el envío.
    """
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")

    if not smtp_user or not smtp_pass:
        return "Error de Configuración: Faltan credenciales SMTP en el servidor. Solo puedo generar borradores por ahora."

    try:
        msg = MIMEText(cuerpo)
        msg['Subject'] = f"[MinCYT AI] {asunto}"
        msg['From'] = smtp_user
        msg['To'] = destinatario

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        return f"✅ Email enviado correctamente a {destinatario}."

    except Exception as e:
        return f"Error enviando email: {str(e)}"