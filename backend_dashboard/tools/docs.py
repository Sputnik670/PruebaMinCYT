import os
import logging
import pandas as pd
from fastapi import UploadFile
from supabase import create_client
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader 
import io
import docx

# Configuración de logs
logger = logging.getLogger(__name__)

# 1. Conexión a Supabase y Gemini
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)

# --- MODELO DE EMBEDDINGS ACTUALIZADO ---
embeddings_model = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004", # <--- CORREGIDO: Modelo más reciente y potente
    task_type="retrieval_document"
)

def procesar_archivo_subido(file: UploadFile):
    """
    Función maestra: Recibe PDF, Excel, Word o TXT, lo guarda en Storage y lo indexa en la BD Vectorial.
    """
    filename = file.filename
    logger.info(f"Procesando archivo: {filename}")
    
    # Leemos el contenido del archivo en memoria
    content = file.file.read()
    file_stream = io.BytesIO(content) 
    
    try:
        ext = filename.lower()
        texto_extraido = ""
        
        # A. Guardar el archivo físico en el Bucket "biblioteca_documentos"
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

        # 1. PDF
        if ext.endswith(".pdf"):
            try:
                reader = PdfReader(file_stream)
                for page in reader.pages:
                    texto_extraido += (page.extract_text() or "") + "\n"
            except Exception as e:
                return False, f"Error leyendo PDF corrupto o encriptado: {str(e)}"
                
        # 2. EXCEL / CSV
        elif ext.endswith((".xlsx", ".xls", ".csv")):
            try:
                if ext.endswith(".csv"):
                    df = pd.read_csv(file_stream)
                else:
                    df = pd.read_excel(file_stream)
                
                # Limpieza de filas vacías (toda la fila)
                df.dropna(how='all', inplace=True)
                
                # Convertir a texto solo si hay contenido real (tu lógica robusta)
                for _, row in df.iterrows():
                    items_fila = []
                    for col, val in row.items():
                        val_str = str(val).strip()
                        if pd.notna(val) and val_str and val_str.lower() not in ['nan', 'false', 'none', '']:
                            items_fila.append(f"{col}: {val_str}")
                    
                    if items_fila:
                        texto_extraido += " | ".join(items_fila) + "\n"
                        
            except Exception as e:
                return False, f"Error leyendo Excel/CSV: {str(e)}"
        
        # 3. WORD (.docx) <--- NUEVO
        elif ext.endswith(".docx"):
            try:
                doc = docx.Document(file_stream)
                texto_extraido = "\n".join([para.text for para in doc.paragraphs])
            except Exception as e:
                return False, f"Error leyendo Word: {str(e)}"

        # 4. TEXTO PLANO (.txt) <--- NUEVO
        elif ext.endswith(".txt"):
            try:
                texto_extraido = content.decode("utf-8")
            except Exception:
                texto_extraido = content.decode("latin-1") # Fallback encoding

        else:
            # La lista final de formatos soportados
            return False, "Formato no soportado. Por favor sube PDF, Excel, Word (.docx), CSV o TXT."

        if not texto_extraido.strip():
            return False, "El archivo parece estar vacío o no se pudo extraer texto legible."

        # C. Dividir texto en trozos (Chunking)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_text(texto_extraido)

        # D. Limpieza de memoria (SEGURIDAD ANTI-DUPLICADOS)
        try:
            logger.info(f"🧹 Limpiando memoria antigua para: {filename}")
            supabase.table("libreria_documentos").delete().match({"metadata": {"source": filename}}).execute()
        except Exception as e:
            logger.warning(f"No se pudo limpiar memoria previa: {e}")

        # E. Vectorizar y Guardar en Base de Datos
        logger.info(f"Indexando {len(chunks)} fragmentos de {filename}...")
        
        registros = []
        for chunk in chunks:
            vector = embeddings_model.embed_query(chunk)
            registros.append({
                "content": chunk,
                "metadata": {"source": filename, "type": file.content_type},
                "embedding": vector
            })
            
        supabase.table("libreria_documentos").insert(registros).execute()
        
        return True, f"✅ Archivo '{filename}' procesado, limpiado e indexado ({len(chunks)} partes)."

    except Exception as e:
        logger.error(f"Error crítico procesando archivo: {e}", exc_info=True)
        return False, f"Error interno: {str(e)}"