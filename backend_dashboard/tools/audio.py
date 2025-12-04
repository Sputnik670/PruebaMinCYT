import os
import tempfile
import shutil
import logging
from pathlib import Path
import google.generativeai as genai
from fastapi import UploadFile, HTTPException

logger = logging.getLogger(__name__)
api_key = os.getenv("GOOGLE_API_KEY")
if api_key: genai.configure(api_key=api_key)

def procesar_audio_gemini(file: UploadFile) -> str:
    try:
        if not api_key: raise ValueError("Falta API Key")
        suffix = Path(file.filename).suffix or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        
        if os.path.getsize(tmp_path) < 1000: raise ValueError("Audio muy corto")
        
        # Modelo 2.0 Flash 001
        model = genai.GenerativeModel('models/gemini-2.0-flash-001')
        audio_file = genai.upload_file(path=tmp_path, mime_type="audio/webm" if suffix == ".webm" else file.content_type)
        
        # Esperar proceso (simple loop)
        import time
        while audio_file.state.name == "PROCESSING": time.sleep(1)
            
        res = model.generate_content(["Transcribe este audio.", audio_file])
        
        try: genai.delete_file(audio_file.name)
        except: pass
        os.remove(tmp_path)
        
        return res.text
    except Exception as e:
        logger.error(f"Error audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))