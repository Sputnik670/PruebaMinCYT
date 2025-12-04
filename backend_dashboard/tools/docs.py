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

# 1. Conexión a Supabase y Gemini
url = os.environ.get("SUPABASE_URL")

# --- CORRECCIÓN DE LÓGICA: PERMISOS ---
# Usamos la Service Role Key para tener permisos de administrador y saltar las políticas RLS
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")

supabase = create_client(url, key)

# --- MODELO DE EMBEDDINGS ---
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
    """
    Limpieza profunda para mejorar la calidad semántica.
    """
    # 1. Eliminar múltiples espacios y saltos de línea excesivos
    texto = re.sub(r'\s+', ' ', texto).strip()
    # 2. Eliminar caracteres no imprimibles raros
    texto = "".join(ch for ch in texto if ch.isprintable())
    return texto

def procesar_archivo_subido(file: UploadFile):
    """
    Función maestra: Recibe PDF, Excel, Word o TXT, lo guarda en Storage y lo indexa.
    """
    filename = file.filename
    logger.info(f"Procesando archivo: {filename}")
    
    content = file.file.read()
    file_stream = io.BytesIO(content) 
    
    try:
        ext = filename.lower()
        texto_extraido = ""
        metadata_extra = {} # Para guardar info como nro de páginas
        
        # A. Guardar en Storage (Backup)
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
                    # Agregamos marcador de página para que el bot sepa citar
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
                # Convertimos tabla a texto estructurado
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

        # C. Limpieza
        texto_limpio = limpiar_texto(texto_extraido)
        if len(texto_limpio) < 10:
            return False, "El archivo está vacío o es ilegible (quizás es una imagen escaneada)."

        # D. Chunking Inteligente (Respetando párrafos)
        # Separadores: Prioriza doble salto de línea (párrafo) antes que punto.
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500, # Aumentamos tamaño para tener más contexto
            chunk_overlap=300,
            separators=["\n--- Pág", "\n\n", "\n", ". ", " ", ""]
        )
        chunks = text_splitter.split_text(texto_extraido) # Usamos el extraído (con marcas de pág)

        # E. Limpieza BD
        try:
            supabase.table("libreria_documentos").delete().match({"metadata": {"source": filename}}).execute()
        except Exception: pass

        # F. Indexado
        logger.info(f"Indexando {len(chunks)} fragmentos...")
        registros = []
        for chunk in chunks:
            # Limpiamos el chunk individualmente para el vector, pero guardamos el texto original
            chunk_clean = limpiar_texto(chunk)
            vector = embeddings_model.embed_query(chunk_clean)
            
            registros.append({
                "content": chunk, # Guardamos con formato (saltos de línea) para lectura humana
                "metadata": {"source": filename, "type": file.content_type, **metadata_extra},
                "embedding": vector
            })
            
        supabase.table("libreria_documentos").insert(registros).execute()
        
        return True, f"✅ Archivo '{filename}' procesado correctamente ({len(chunks)} fragmentos)."

    except Exception as e:
        logger.error(f"Error crítico upload: {e}", exc_info=True)
        return False, f"Error interno: {str(e)}"