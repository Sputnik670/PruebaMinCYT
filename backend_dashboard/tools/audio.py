import os
import time
import tempfile
import shutil
import logging
from pathlib import Path
import google.generativeai as genai
from fastapi import UploadFile, HTTPException

# Nota: El import de guardar_acta se mantiene por compatibilidad
try:
    from .database import guardar_acta
except ImportError:
    from backend_dashboard.tools.database import guardar_acta

# Configurar logger local
logger = logging.getLogger(__name__)

# 1. CONFIGURACIÓN DE LA API KEY
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    logger.error("❌ ERROR CRÍTICO: No se encontró GOOGLE_API_KEY.")
else:
    genai.configure(api_key=api_key)

def procesar_audio_gemini(file: UploadFile) -> str:
    """
    Recibe un archivo de audio, valida su integridad y lo transcribe con Gemini 1.5 Flash.
    """
    tmp_path = None
    
    try:
        if not api_key:
            raise ValueError("La API Key de Google no está configurada.")

        # 2. Guardar temporalmente y VALIDAR TAMAÑO
        suffix = Path(file.filename).suffix or ".webm"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
            
        # Verificar tamaño del archivo
        file_size = os.path.getsize(tmp_path)
        logger.info(f"🎙️ Archivo guardado: {tmp_path} | Tamaño: {file_size} bytes")
        
        if file_size < 1000: 
            raise ValueError(f"El audio grabado es demasiado corto ({file_size} bytes).")

        try:
            # 3. Subir a Gemini con MimeType EXPLÍCITO
            logger.info(f"Subiendo a Gemini (Mime: {file.content_type})...")
            mime = "audio/webm" if suffix == ".webm" else file.content_type
            
            audio_file = genai.upload_file(path=tmp_path, mime_type=mime)
            
            # 4. Esperar procesamiento
            logger.info("⏳ Esperando procesamiento en la nube...")
            while audio_file.state.name == "PROCESSING":
                time.sleep(1)
                audio_file = genai.get_file(audio_file.name)
            
            if audio_file.state.name == "FAILED":
                raise ValueError("Gemini rechazó el archivo de audio.")
            
            logger.info(f"✅ Audio listo: {audio_file.name}")

            # 5. Generar contenido (Transcripción)
            # CORRECCIÓN: Usamos el modelo 1.5 Flash
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = (
                "Transcribe este audio con precisión. "
                "Si identificas distintos hablantes, trata de diferenciarlos. "
                "Si es una reunión, genera un texto corrido y coherente."
            )

            response = model.generate_content([prompt, audio_file])
            texto_transcrito = response.text 
            
            return texto_transcrito

        finally:
            # Limpieza de archivo local y de la API
            if 'audio_file' in locals():
                try:
                    genai.delete_file(audio_file.name)
                    logger.info(f"🗑️ Archivo temporal de Gemini eliminado: {audio_file.name}")
                except Exception as e:
                    logger.warning(f"No se pudo eliminar archivo de Gemini: {e}")
                    
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        logger.error(f"❌ Error en procesar_audio_gemini: {str(e)}", exc_info=True)
        msg_error = str(e)
        if "400" in msg_error: msg_error = "Error de formato de audio."
        raise HTTPException(status_code=500, detail=msg_error)