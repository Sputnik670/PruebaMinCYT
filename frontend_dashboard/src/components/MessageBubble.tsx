import React from 'react';
import { Message } from '../types/types'; // Ajusta la ruta si creaste la carpeta types
import { Bot, User } from 'lucide-react';

interface MessageBubbleProps {
  message: Message;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isBot = message.sender === 'bot';

  return (
    <div className={`flex w-full mb-4 ${isBot ? 'justify-start' : 'justify-end'} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
      <div className={`flex max-w-[85%] md:max-w-[75%] ${isBot ? 'flex-row' : 'flex-row-reverse'} items-start gap-3`}>

        {/* Icono del Avatar */}
        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-sm ${
            isBot ? 'bg-white border border-slate-200 text-blue-700' : 'bg-blue-600 text-blue-100'
          }`}>
          {isBot ? <Bot size={18} /> : <User size={18} />}
        </div>

        {/* Burbuja de Texto */}
        <div className={`p-4 rounded-2xl text-sm shadow-sm leading-relaxed ${
            isBot
            ? 'bg-white border border-slate-200 text-slate-700 rounded-tl-none'
            : 'bg-blue-600 text-white rounded-tr-none'
          }`}>
          <p className="whitespace-pre-wrap">{message.text}</p>
          
          {/* Hora del mensaje (opcional, pequeño detalle visual) */}
          <span className={`text-[10px] block mt-2 opacity-70 ${isBot ? 'text-slate-400' : 'text-blue-200'}`}>
            {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>

      </div>
    </div>
  );
};