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

// --- INTERFAZ ACTUALIZADA (Sincronizada con Supabase) ---
export interface AgendaItem {
  id?: number;          // ID numérico autogenerado (opcional)
  id_hash?: string;     // 🔥 NUEVO: Hash único (MD5) usado como key en React
  
  fecha: string;        // Fecha de INICIO (ISO string YYYY-MM-DD)
  fecha_fin?: string;   // Fecha de FIN (Opcional)
  
  titulo: string;
  lugar?: string;       // Puede venir vacío, mejor opcional
  ambito?: string;      // "Oficial", "Nacional", etc.
  
  // Datos Financieros / Administrativos
  funcionario?: string;
  costo?: number;
  moneda?: string;      // "ARS", "USD", "EUR"
  
  num_expediente?: string;
  estado?: string;
  
  // Datos Públicos
  organizador?: string;
  participantes?: string;
  
  // 🔥 CAMBIO CLAVE: Ahora es string libre porque el Python pone nombres de pestañas
  origen_dato?: string; 
  
  // Índice para propiedades extra que puedan venir de Supabase
  [key: string]: any;
}