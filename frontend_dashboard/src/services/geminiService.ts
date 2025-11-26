// src/services/geminiService.ts (VERSIÓN CORREGIDA PARA USAR TU BACKEND)

// Asegúrate de que esta URL sea la de tu backend en Render (sin barra al final)
// Si estás en local probando backend y frontend a la vez, usa "http://127.0.0.1:8000"
const API_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export const sendMessageToGemini = async (message: string) => {
   // ... el resto sigue igual, usando API_URL
  try {
    const response = await fetch(`${API_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      // Tu backend espera un JSON con la clave "message" según main.py
      body: JSON.stringify({ message: message }),
    });

    if (!response.ok) {
      throw new Error(`Error del servidor: ${response.status}`);
    }

    const data = await response.json();
    
    // Tu backend devuelve {"response": "texto de respuesta"}
    return data.response; 
  } catch (error) {
    console.error("Error conectando con el Backend:", error);
    throw error;
  }
};