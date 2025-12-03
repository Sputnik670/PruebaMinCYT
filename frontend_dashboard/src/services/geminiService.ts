// src/services/geminiService.ts

import { Message } from '../types/types'; 

// Configuración robusta de la URL
const rawUrl = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
const API_URL = rawUrl.replace(/\/api\/?$/, "").replace(/\/$/, "");

// --- FUNCIÓN 1: CHAT DE TEXTO CON STREAMING ---
export const sendMessageToGemini = async (
  message: string, 
  history: Message[], 
  onStreamUpdate: (chunk: string) => void, // Callback para ir enviando el texto
  sessionId?: string | null // Recibimos el ID de sesión opcional
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
      // Enviamos session_id al backend
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

    // --- LÓGICA DE STREAMING MEJORADA (CON BUFFER Y PARSEO JSON) ---
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let done = false;
    let buffer = ""; 

    while (!done) {
      const { value, done: doneReading } = await reader.read();
      done = doneReading;
      
      if (value) {
        // 1. Acumulamos lo que llega al buffer
        buffer += decoder.decode(value, { stream: true });
        
        // 2. Buscamos separadores de evento completos (doble enter es el estándar SSE)
        const parts = buffer.split("\n\n");
        
        // 3. Guardamos el último fragmento (posiblemente incompleto) para la siguiente vuelta
        buffer = parts.pop() || ""; 
        
        // 4. Procesamos solo las partes que llegaron completas
        for (const part of parts) {
            // Verificamos el prefijo estándar de SSE "data: "
            if (part.startsWith("data: ")) {
                const rawData = part.slice(6); // Quitamos "data: " de forma segura
                
                // --- 🛡️ AQUÍ ESTÁ EL CAMBIO CLAVE PARA CORREGIR EL CORTE DE TEXTO ---
                try {
                    // Intentamos leer como JSON primero (formato seguro)
                    if (rawData.trim().startsWith("{")) {
                        const parsed = JSON.parse(rawData);
                        if (parsed.text) {
                            onStreamUpdate(parsed.text);
                        }
                    } else {
                        // Soporte Legacy / SESSION_ID (Texto plano)
                        onStreamUpdate(rawData);
                    }
                } catch (e) {
                    // Si falla el parseo JSON, mandamos el texto crudo (ej: errores o IDs simples)
                    onStreamUpdate(rawData);
                }
            }
        }
      }
    }
    
    return true; 

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