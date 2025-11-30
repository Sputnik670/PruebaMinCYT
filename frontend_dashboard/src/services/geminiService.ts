// src/services/geminiService.ts

// [NUEVA LÍNEA] Importamos el tipo Message
import { Message } from '../types/types'; 

// Configuración robusta: Elimina barras extra o '/api' al final para evitar errores de ruta
const rawUrl = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const API_URL = rawUrl.replace(/\/api\/?$/, "").replace(/\/$/, "");

// --- FUNCIÓN 1: CHAT DE TEXTO ---
// MODIFICACIÓN: ACEPTA 'history' como arreglo de Message
export const sendMessageToGemini = async (message: string, history: Message[]) => {
  
  // [NUEVO] Serialización del historial para enviarlo como JSON
  const serializedHistory = history.map(msg => ({
    text: msg.text,
    sender: msg.sender,
    // Usamos toISOString para enviar la fecha como string serializable
    timestamp: msg.timestamp.toISOString(), 
  }));

  try {
    // Nota: Mantenemos /api/chat porque así lo definiste en main.py
    const response = await fetch(`${API_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      // [MODIFICADO] Incluye el mensaje y el historial serializado
      body: JSON.stringify({ message: message, history: serializedHistory }), 
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
// [CORREGIDA PARA COINCIDIR CON EL BACKEND]
export const sendAudioToGemini = async (audioBlob: Blob) => {
  const formData = new FormData();
  formData.append('file', audioBlob, 'recording.webm');

  try {
    console.log(`Enviando audio a: ${API_URL}/upload-audio/`);
    
    // CAMBIO AQUÍ: Apuntamos a /upload-audio/ en lugar de /api/voice
    const response = await fetch(`${API_URL}/upload-audio/`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Error de audio: ${response.status}`);
    }

    const data = await response.json();
    // CAMBIO AQUÍ: El backend nuevo devuelve "transcripcion", no "text"
    return data.transcripcion || "Transcripción no disponible."; 
    
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
    // Nota: Mantenemos /api/upload
    const response = await fetch(`${API_URL}/api/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Error al subir: ${response.status}`);
    }

    const data = await response.json();
    return data.message;
  } catch (error) {
    console.error("Error subiendo archivo:", error);
    throw error;
  }
};