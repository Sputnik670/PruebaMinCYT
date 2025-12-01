# backend_dashboard/monitoring/session_manager.py
from supabase import create_client, Client
from datetime import datetime
from typing import Optional, List, Dict, Any
import json
import uuid
import os

class SessionManager:
    def __init__(self):
        """Inicializar con credenciales de Supabase desde variables de entorno"""
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not supabase_url or not supabase_key:
            print("⚠️ WARNING: Credenciales de Supabase no encontradas en .env")
            self.supabase = None
        else:
            self.supabase = create_client(supabase_url, supabase_key)
    
    def crear_nueva_sesion(self, user_id: str = "usuario_anonimo", titulo: str = "Nueva conversación") -> str:
        """Crear una nueva sesión de chat"""
        try:
            if not self.supabase:
                return str(uuid.uuid4())  # Fallback sin BD
                
            nueva_sesion = {
                "user_id": user_id,
                "titulo_sesion": titulo,
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat()
            }
            
            response = self.supabase.table("sesiones_chat").insert(nueva_sesion).execute()
            session_id = response.data[0]["id"]
            print(f"✅ Nueva sesión creada: {session_id}")
            return session_id
            
        except Exception as e:
            print(f"❌ Error creando sesión: {e}")
            return str(uuid.uuid4())  # Fallback
    
    def guardar_mensaje(self, sesion_id: str, mensaje_usuario: str, respuesta_bot: str, herramientas_usadas: List[str] = []):
        """Guardar un intercambio de mensajes"""
        try:
            if not self.supabase:
                return
                
            mensaje = {
                "sesion_id": sesion_id,
                "mensaje_usuario": mensaje_usuario,
                "respuesta_bot": respuesta_bot,
                "herramientas_usadas": herramientas_usadas,
                "timestamp": datetime.now().isoformat()
            }
            
            # Guardar mensaje
            self.supabase.table("mensajes_sesion").insert(mensaje).execute()
            
            # Actualizar última actividad
            self.supabase.table("sesiones_chat").update({
                "last_active": datetime.now().isoformat()
            }).eq("id", sesion_id).execute()
            
            print(f"💾 Mensaje guardado en sesión: {sesion_id}")
            
        except Exception as e:
            print(f"❌ Error guardando mensaje: {e}")
    
    def obtener_historial_sesion(self, sesion_id: str, limite: int = 10) -> List[Dict]:
        """Obtener el historial de una sesión"""
        try:
            if not self.supabase:
                return []
                
            response = self.supabase.table("mensajes_sesion")\
                .select("*")\
                .eq("sesion_id", sesion_id)\
                .order("timestamp", desc=False)\
                .limit(limite)\
                .execute()
            
            historial = response.data if response.data else []
            print(f"📖 Recuperado historial: {len(historial)} mensajes")
            return historial
            
        except Exception as e:
            print(f"❌ Error obteniendo historial: {e}")
            return []
    
    def listar_sesiones_usuario(self, user_id: str, limite: int = 20) -> List[Dict]:
        """Listar sesiones recientes de un usuario"""
        try:
            if not self.supabase:
                return []
                
            response = self.supabase.table("sesiones_chat")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("last_active", desc=True)\
                .limit(limite)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            print(f"❌ Error listando sesiones: {e}")
            return []

# Instancia global que se usará en toda la aplicación
session_manager = SessionManager()