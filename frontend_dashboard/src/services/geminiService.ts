// src/services/geminiService.ts

import { Message } from '../types/types'; 

// Configuración robusta de la URL (Estandarizada a 127.0.0.1 para evitar problemas de DNS/IPv6)
const rawUrl = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
const API_URL = rawUrl.replace(/\/api\/?$/, "").replace(/\/$/, "");

// --- FUNCIÓN 1: CHAT DE TEXTO CON STREAMING ---
export const sendMessageToGemini = async (
  message: string, 
  history: Message[], 
  onStreamUpdate: (chunk: string) => void, // Callback para ir enviando el texto
  sessionId?: string | null // <--- NUEVO: Recibimos el ID de sesión opcional
) => {
  
  // Serialización correcta con ID para el historial visual
  const serializedHistory = history.map(msg => ({
    id: msg.id,
    text: msg.text,
    sender: msg.sender,
    timestamp: msg.timestamp.toISOString(), 
  }));

  try {
    const response = await fetch(`${API_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      // <--- CAMBIO CLAVE: Enviamos session_id al backend
      body: JSON.stringify({ 
          message: message, 
          history: serializedHistory,
          session_id: sessionId || null 
      }), 
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      console.error("Detalle del error del servidor:", errorData);
      throw new Error(`Error del servidor: ${response.status} - ${JSON.stringify(errorData)}`);
    }

    if (!response.body) throw new Error("La respuesta no tiene cuerpo para leer (stream).");

    // --- LÓGICA DE STREAMING ---
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let done = false;

    while (!done) {
      const { value, done: doneReading } = await reader.read();
      done = doneReading;
      
      if (value) {
        const chunk = decoder.decode(value, { stream: true });
        
        // Limpiamos prefijos de protocolo si llegaran a colarse en el texto visible
        // (Aunque ChatInterface ya maneja "data: SESSION_ID:", esto es por seguridad)
        const cleanChunk = chunk.replace(/^data: /gm, "");
        
        onStreamUpdate(cleanChunk); 
      }
    }
    
    return true; // Indicamos éxito al finalizar

  } catch (error) {
    console.error("Error conectando con el Backend:", error);
    throw error;
  }
};

// --- FUNCIÓN 2: ENVIAR AUDIO (VOZ) ---
export const sendAudioToGemini = async (audioBlob: Blob) => {
  const formData = new FormData();
  formData.append('file', audioBlob, 'recording.webm');

  try {
    console.log(`Enviando audio a: ${API_URL}/upload-audio/`);
    
    const response = await fetch(`${API_URL}/upload-audio/`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Error de audio: ${response.status}`);
    }

    const data = await response.json();
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