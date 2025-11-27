import os
from langchain.tools import tool
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
import tempfile

# Variable global para almacenar la "memoria" del documento actual en RAM
VECTORSTORE_ACTUAL = None

def procesar_pdf_subido(archivo_upload):
    """
    Recibe un archivo PDF, lo lee y crea un índice de búsqueda.
    """
    global VECTORSTORE_ACTUAL
    
    try:
        # 1. Guardar el PDF temporalmente
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(archivo_upload.file.read())
            tmp_path = tmp_file.name

        # 2. Cargar y extraer texto
        loader = PyPDFLoader(tmp_path)
        docs = loader.load()
        
        # 3. Dividir en fragmentos
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        splits = text_splitter.split_documents(docs)
        
        # 4. Vectorizar (Embeddings)
        embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
        
        # 5. Crear el buscador
        VECTORSTORE_ACTUAL = FAISS.from_documents(splits, embeddings)
        
        # Limpieza
        os.remove(tmp_path)
        return True, f"PDF procesado correctamente. {len(splits)} fragmentos indexados."
        
    except Exception as e:
        return False, f"Error procesando PDF: {str(e)}"

@tool
def consultar_documento(pregunta: str) -> str:
    """
    Útil para responder preguntas BASADAS en el documento PDF que el usuario acaba de subir.
    Usa esta herramienta cuando el usuario pregunte sobre 'el archivo', 'el pdf', 'el documento' o 'el reglamento'.
    """
    global VECTORSTORE_ACTUAL
    
    if not VECTORSTORE_ACTUAL:
        return "No hay ningún documento cargado actualmente. Pide al usuario que suba un PDF primero."
    
    try:
        # Buscamos los 4 fragmentos más relevantes
        retriever = VECTORSTORE_ACTUAL.as_retriever(search_kwargs={"k": 4})
        docs = retriever.invoke(pregunta)
        
        # Unimos los fragmentos
        contexto = "\n\n".join([d.page_content for d in docs])
        return f"Información encontrada en el documento:\n{contexto}"
        
    except Exception as e:
        return f"Error al consultar el documento: {str(e)}"