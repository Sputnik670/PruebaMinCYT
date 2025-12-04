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
import re

# Configuración de logs
logger = logging.getLogger(__name__)

# 1. Conexión a Supabase
url = os.environ.get("SUPABASE_URL")
# Usamos Service Role para poder escribir/borrar sin restricciones RLS
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

try:
    supabase = create_client(url, key)
except Exception as e:
    logger.error(f"Error conectando a Supabase: {e}")
    supabase = None

# 2. Modelo de Embeddings (Text-to-Vector)
try:
    embeddings_model = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004", 
        task_type="retrieval_document"
    )
except Exception:
    logger.warning("⚠️ Modelo 004 no disponible, usando fallback a embedding-001")
    embeddings_model = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001", 
        task_type="retrieval_document"
    )

def limpiar_texto(texto: str) -> str:
    """Limpieza profunda para mejorar la calidad semántica."""
    # 1. Eliminar caracteres no imprimibles pero mantener saltos de línea básicos
    texto = re.sub(r'[^\x20-\x7E\náéíóúÁÉÍÓÚñÑüÜ]', '', texto)
    # 2. Unificar múltiples espacios en uno solo
    texto = re.sub(r'[ \t]+', ' ', texto)
    # 3. Eliminar saltos de línea repetidos (más de 2)
    texto = re.sub(r'\n{3,}', '\n\n', texto)
    return texto.strip()

def procesar_archivo_subido(file: UploadFile):
    """
    Recibe PDF, Excel, Word o TXT, extrae el texto, lo divide y lo guarda vectorializado.
    """
    if not supabase:
        return False, "Error de configuración: Base de datos no disponible."

    filename = file.filename
    logger.info(f"Procesando archivo: {filename}")
    
    content = file.file.read()
    file_stream = io.BytesIO(content) 
    
    try:
        ext = filename.lower()
        texto_extraido = ""
        metadata_extra = {} 
        
        # A. Guardar copia física en Storage (Backup opcional)
        try:
            supabase.storage.from_("biblioteca_documentos").upload(
                path=filename,
                file=content,
                file_options={"content-type": file.content_type, "x-upsert": "true"}
            )
        except Exception as e:
            logger.warning(f"Nota Storage: {e}")

        # B. Extracción de Texto por Tipo
        if ext.endswith(".pdf"):
            try:
                reader = PdfReader(file_stream)
                metadata_extra["pages"] = len(reader.pages)
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text() or ""
                    # Marca de página crítica para citas
                    texto_extraido += f"\n--- Pág {i+1} ---\n{page_text}"
            except Exception as e:
                return False, f"Error leyendo PDF: {str(e)}"
                
        elif ext.endswith((".xlsx", ".xls", ".csv")):
            try:
                if ext.endswith(".csv"):
                    df = pd.read_csv(file_stream)
                else:
                    df = pd.read_excel(file_stream)
                
                df.dropna(how='all', inplace=True)
                texto_extraido = df.to_string(index=False)
            except Exception as e:
                return False, f"Error leyendo Excel: {str(e)}"
        
        elif ext.endswith(".docx"):
            try:
                doc = docx.Document(file_stream)
                texto_extraido = "\n".join([para.text for para in doc.paragraphs])
            except Exception as e:
                return False, f"Error leyendo Word: {str(e)}"

        elif ext.endswith(".txt"):
            texto_extraido = content.decode("utf-8", errors="ignore")

        else:
            return False, "Formato no soportado."

        # C. Limpieza y Validación
        texto_limpio = limpiar_texto(texto_extraido)
        if len(texto_limpio) < 50: # Umbral mínimo
            return False, "El archivo parece estar vacío o es una imagen escaneada sin texto."

        # D. Chunking (División inteligente)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,    # Tamaño ideal para contexto semántico
            chunk_overlap=300,  # Solapamiento para no perder contexto entre cortes
            separators=["\n--- Pág", "\n\n", "\n", ". ", " ", ""]
        )
        chunks = text_splitter.split_text(texto_extraido) # Usamos el texto con marcas de pág

        # E. Limpieza BD (Evitar duplicados)
        try:
            # Borrar chunks viejos del mismo archivo
            supabase.table("libreria_documentos").delete().match({"metadata": {"source": filename}}).execute()
        except Exception: pass

        # F. Indexado Vectorial
        logger.info(f"Indexando {len(chunks)} fragmentos para '{filename}'...")
        registros = []
        
        # Procesamos en lotes si son muchos chunks
        for chunk in chunks:
            # Vectorizamos texto limpio, pero guardamos el texto original con formato para lectura humana
            chunk_clean = limpiar_texto(chunk)
            vector = embeddings_model.embed_query(chunk_clean)
            
            registros.append({
                "content": chunk, 
                "metadata": {"source": filename, "type": file.content_type, **metadata_extra},
                "embedding": vector
            })
            
        # Inserción (Supabase maneja batch inserts bien, pero si es gigante conviene dividir)
        if registros:
            supabase.table("libreria_documentos").insert(registros).execute()
        
        return True, f"✅ Archivo '{filename}' procesado e indexado ({len(chunks)} fragmentos)."

    except Exception as e:
        logger.error(f"Error crítico upload: {e}", exc_info=True)
        return False, f"Error interno procesando archivo: {str(e)}"