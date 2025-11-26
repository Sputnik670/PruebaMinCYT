// src/services/geminiService.ts (VERSIÓN CORREGIDA Y LIMPIA)

import { GoogleGenerativeAI } from "@google/generative-ai";

// Línea corregida para cargar la variable VITE_GOOGLE_API_KEY del archivo .env
const API_KEY = import.meta.env.VITE_GOOGLE_API_KEY; 

const genAI = new GoogleGenerativeAI(API_KEY);

// La base de conocimiento inyectada a partir del Calendario CSV
const CALENDAR_DATA = `
--- CALENDARIO DE EVENTOS CLAVE MINCYT 2025/2026 ---
| Título | Fecha inicio | Fecha fin | Lugar | Participante/s |
| :--- | :--- | :--- | :--- | :--- |
| World Economic Forum Annual Meeting 2025 | 2025-01-20 | 2025-01-24 | Davos, Suiza | Darío Genua |
| Cumbre de Acción sobre Inteligencia Artificial | 2025-02-10 | 2025-02-11 | París, Francia | César Gazzo/Dario Genua |
| GSMA - MWC Barcelona 2025 | 2025-03-02 | 2025-03-05 | Barcelona, España | Darío Genua/Mariano Mussa/Mariano Greco/Ozores |
| Space-Comm Expo | 2025-03-11 | 2025-03-12 | Londres, Reino Unido | Darío Genua/Mariano Mussa |
| Consultas Espaciales Estratégicas USA/ARG | 2025-03-11 | 2025-03-13 | Washington, USA | Emiliano Cisneros |
| Diálogos Anuales de Políticas Digitales | 2025-04-02 | 2025-04-03 | Ciudad de México, México | Darío Genua |
| CyberTech Chile 2025 | 2025-05-13 | 2025-05-14 | Santiago de Chile, Chile | Darío Genua/Natalia Avendaño |
| Google I/O | 2025-05-20 | 2025-05-21 | California, USA | Darío Genua/Mariano Mussa/Emiliano Cisneros |
| Council ITU 2025 | 2025-06-17 | 2025-06-27 | Ginebra, Suiza | Darío Genua/Martín Ozores |
| Cumbre Mundial sobre la Sociedad de la Información | 2025-07-07 | 2025-07-11 | Ginebra, Suiza | Martín Ozores |
| Reunión Ministerial G20 Task Force IA | 2025-09-29 | 2025-09-30 | Ciudad del Cabo, Sudáfrica | Dario Genua / EC |
| World Nuclear Exhibition | 2025-11-04 | 2025-11-06 | París, Francia | Darío Genua/Mariano Mussa |
| STS Forum | 2025-12-03 | 2025-12-05 | Cuernavaca, MEX | No vamos |
| Cumbre Mundial de Gobiernos 2026 | 2026-02-03 | 2026-02-05 | Dubai | Darío Genua |
| Mobile World Congress 2026 | 2026-03-02 | 2026-03-04 | Barcelona | Ozores + Brunelli + Ottati |
`; // Fin del CALENDAR_DATA

// Aquí definimos la personalidad y las reglas del bot
const SYSTEM_INSTRUCTION = `
Eres el asistente virtual del MinCYT (Ministerio de Ciencia, Tecnología e Innovación).
Tu tono es profesional e institucional.
Tu principal fuente de información sobre eventos oficiales es el siguiente calendario:

${CALENDAR_DATA}

Instrucciones:
1. Responde preguntas sobre fechas, lugares y participantes ÚNICAMENTE usando la información del calendario proporcionado.
2. Si un evento está en el calendario, NO digas que no puedes predecir el futuro; proporciona la fecha y los participantes.
3. Si la información solicitada NO está en el calendario, o si el calendario indica 'No vamos', informa al usuario que no tienes esa información.
`;

export const sendMessageToGemini = async (message: string) => {
  try {
    // Usamos el modelo "flash" porque es muy rápido para chats
    const model = genAI.getGenerativeModel({
      model: "gemini-2.5-flash",
      systemInstruction: SYSTEM_INSTRUCTION,
    });

    const result = await model.generateContent(message);
    const response = await result.response;
    return response.text();
  } catch (error) {
    console.error("Error conectando con Gemini:", error);
    throw error;
  }
};