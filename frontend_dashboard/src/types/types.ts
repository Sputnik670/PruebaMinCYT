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

// --- INTERFAZ ACTUALIZADA (MULTIMONEDA) ---
export interface AgendaItem {
  id?: number;
  fecha: string;
  titulo: string;
  lugar: string;
  ambito: string;
  funcionario?: string;
  
  // NUEVOS CAMPOS (Reemplazan a costo_ars)
  costo?: number;
  moneda?: string; // Puede ser "ARS", "USD", "EUR"
  
  num_expediente?: string;
  estado?: string;
  organizador?: string;
  participantes?: string;
  origen_dato: 'MisionesOficiales' | 'CalendarioPublico';
}