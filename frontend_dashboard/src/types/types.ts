// src/types/types.ts

export interface Message {
  id: string;
  text: string;
  sender: 'user' | 'bot';
  timestamp: Date;
}

export interface ChatState {
  messages: Message[];
  isLoading: boolean;
}

// --- INTERFAZ ACTUALIZADA (MULTIMONEDA Y RANGOS DE FECHA) ---
export interface AgendaItem {
  id?: number;
  fecha: string;      // Fecha de INICIO
  fecha_fin?: string; // Fecha de FIN (Nuevo campo opcional)
  titulo: string;
  lugar: string;
  ambito: string;
  
  // Campos opcionales
  funcionario?: string;
  costo?: number;
  moneda?: string;    // "ARS", "USD", "EUR"
  
  num_expediente?: string;
  estado?: string;
  organizador?: string;
  participantes?: string;
  
  origen_dato: 'MisionesOficiales' | 'CalendarioPublico';
}