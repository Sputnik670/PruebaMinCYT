import os
import logging
import pandas as pd
from fastapi import UploadFile
from supabase import create_client
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader # <--- CORRECCIÓN: Usamos pypdf (la librería moderna)
import io

# Configuración de logs
logger = logging.getLogger(__name__)

# 1. Conexión a Supabase y Gemini
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)

embeddings_model = GoogleGenerativeAIEmbeddings(
    model="models/embedding-001", 
    task_type="retrieval_document"
)

def procesar_archivo_subido(file: UploadFile):
    """
    Función maestra: Recibe PDF o Excel, lo guarda en Storage y lo indexa en la BD Vectorial.
    """
    filename = file.filename
    logger.info(f"Procesando archivo: {filename}")
    
    # Leemos el contenido del archivo en memoria
    content = file.file.read()
    file_stream = io.BytesIO(content) 
    
    try:
        # A. Guardar el archivo físico en el Bucket "biblioteca_documentos"
        # Nota: Si el bucket no existe o es privado, esto podría fallar, pero seguimos con el indexado.
        try:
            logger.info(f"Subiendo {filename} al Storage...")
            supabase.storage.from_("biblioteca_documentos").upload(
                path=filename,
                file=content,
                file_options={"content-type": file.content_type, "x-upsert": "true"}
            )
        except Exception as e:
            logger.warning(f"Nota sobre Storage (no crítico): {e}")

        # B. Extraer Texto según el tipo
        texto_extraido = ""
        if filename.lower().endswith(".pdf"):
            try:
                reader = PdfReader(file_stream)
                for page in reader.pages:
                    texto_extraido += (page.extract_text() or "") + "\n"
            except Exception as e:
                return False, f"Error leyendo PDF corrupto o encriptado: {str(e)}"
                
        elif filename.lower().endswith((".xlsx", ".xls", ".csv")):
            try:
                if filename.lower().endswith(".csv"):
                    df = pd.read_csv(file_stream)
                else:
                    df = pd.read_excel(file_stream)
                
                # Convertimos cada fila en texto legible
                for _, row in df.iterrows():
                    fila_texto = " | ".join([f"{col}: {val}" for col, val in row.items() if pd.notna(val)])
                    texto_extraido += fila_texto + "\n"
            except Exception as e:
                return False, f"Error leyendo Excel/CSV: {str(e)}"
        
        else:
            return False, "Formato no soportado. Por favor sube PDF, Excel (.xlsx) o CSV."

        if not texto_extraido.strip():
            return False, "El archivo parece estar vacío o no se pudo extraer texto legible."

        # C. Dividir texto en trozos (Chunking)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_text(texto_extraido)

        # D. Vectorizar y Guardar en Base de Datos
        logger.info(f"Indexando {len(chunks)} fragmentos de {filename}...")
        
        registros = []
        for chunk in chunks:
            vector = embeddings_model.embed_query(chunk)
            registros.append({
                "content": chunk,
                "metadata": {"source": filename, "type": file.content_type},
                "embedding": vector
            })
            
        # Insertar en lotes (Supabase)
        supabase.table("libreria_documentos").insert(registros).execute()
        
        return True, f"✅ Archivo '{filename}' procesado e indexado correctamente ({len(chunks)} partes)."

    except Exception as e:
        logger.error(f"Error crítico procesando archivo: {e}", exc_info=True)
        return False, f"Error interno: {str(e)}"