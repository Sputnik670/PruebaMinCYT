import os
import tempfile
import shutil
from pathlib import Path
import google.generativeai as genai
from fastapi import UploadFile, HTTPException

# Asegúrate de configurar tu API KEY aquí o que esté en variables de entorno
# genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def procesar_audio_gemini(file: UploadFile) -> str:
    """
    Recibe un archivo de audio, lo sube a Gemini y solicita 
    transcripción con traducción al español si es necesario.
    """
    try:
        # 1. Guardar el archivo temporalmente en disco
        # Gemini File API necesita un path físico por ahora
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        try:
            # 2. Subir el archivo a Gemini
            print(f"🎙️ Subiendo audio: {file.filename}...")
            audio_file = genai.upload_file(path=tmp_path)
            
            # 3. Configurar el modelo (usamos Flash por velocidad)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # 4. Prompt específico para Transcripción + Traducción
            prompt = (
                "Por favor, escucha este audio atentamente. "
                "Tu tarea es realizar una transcripción fiel. "
                "REGLA IMPORTANTE: Si el audio está en un idioma distinto al español, "
                "proporciona primero la transcripción original y luego su traducción al español. "
                "Si ya está en español, solo entrégame la transcripción literal."
            )

            # 5. Generar contenido
            response = model.generate_content([prompt, audio_file])
            
            # Limpieza: Eliminar archivo de Gemini (opcional, pero buena práctica) y local
            # audio_file.delete() # Si quieres borrarlo de la nube inmediatamente
            
            return response.text

        finally:
            # Borrar archivo temporal local
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    except Exception as e:
        print(f"❌ Error procesando audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error procesando audio: {str(e)}")