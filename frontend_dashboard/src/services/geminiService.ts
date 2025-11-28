// src/services/geminiService.ts

// Usamos la variable de entorno para producción o localhost para desarrollo
const API_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

// --- FUNCIÓN 1: CHAT DE TEXTO ---
export const sendMessageToGemini = async (message: string) => {
  try {
    const response = await fetch(`${API_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message: message }),
    });

    if (!response.ok) {
      throw new Error(`Error del servidor: ${response.status}`);
    }

    const data = await response.json();
    return data.response;
  } catch (error) {
    console.error("Error conectando con el Backend:", error);
    throw error;
  }
};

// --- FUNCIÓN 2: ENVIAR AUDIO (VOZ) ---
export const sendAudioToGemini = async (audioBlob: Blob) => {
  const formData = new FormData();
  // Es importante ponerle nombre y extensión al archivo
  formData.append('file', audioBlob, 'recording.webm'); 

  try {
    const response = await fetch(`${API_URL}/api/voice`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `Error de audio: ${response.status}`);
    }

    const data = await response.json();
    return data.text; // Retorna la transcripción
  } catch (error) {
    console.error("Error enviando audio:", error);
    throw error;
  }
};

// --- FUNCIÓN 3: SUBIR PDF ---
export const uploadFile = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file); 

  try {
    const response = await fetch(`${API_URL}/api/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `Error al subir: ${response.status}`);
    }

    const data = await response.json();
    return data.message; 
  } catch (error) {
    console.error("Error subiendo archivo:", error);
    throw error;
  }
};