import React, { useState, useRef, useEffect } from 'react';
import { Message } from '../types/types'; // Ajusta si tu archivo se llama diferente
import { sendMessageToGemini } from '../services/geminiService';
import { MessageBubble } from './MessageBubble';
import { Send, Loader2, Bot } from 'lucide-react';

export const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: '¡Hola! Soy el asistente virtual del MinCYT. ¿En qué puedo ayudarte hoy respecto a ciencia, tecnología o innovación?',
      sender: 'bot',
      timestamp: new Date()
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll hacia abajo cuando hay mensajes nuevos
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userText = inputValue.trim();
    setInputValue('');

    // 1. Agregar mensaje del usuario
    const userMessage: Message = {
      id: Date.now().toString(),
      text: userText,
      sender: 'user',
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // 2. Llamar a Gemini
      const responseText = await sendMessageToGemini(userText);

      // 3. Agregar respuesta del bot
      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: responseText,
        sender: 'bot',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error("Error:", error);
      // Mensaje de error amigable
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: "Lo siento, tuve un problema de conexión. Por favor intenta de nuevo.",
        sender: 'bot',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // Enviar con Enter
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex flex-col min-h-[600px] bg-slate-50 font-sans">
      
      {/* --- ENCABEZADO --- */}
      <header className="bg-[#002f6c] text-white p-4 shadow-md flex items-center gap-3">
        <div className="p-2 bg-white/10 rounded-full">
            <Bot size={24} />
        </div>
        <div>
            <h1 className="font-bold text-lg">MinCYT Asistente Virtual</h1>
            <p className="text-xs text-blue-200">Ministerio de Ciencia, Tecnología e Innovación</p>
        </div>
      </header>

      {/* --- ÁREA DE CHAT --- */}
      <div className="flex-1 max-h-[calc(100vh - 200px)] overflow-y-auto p-4 md:p-8 w-full max-w-4xl mx-auto scrollbar-hide">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* Animación de "Escribiendo..." */}
        {isLoading && (
          <div className="flex justify-start w-full mb-6 animate-pulse">
            <div className="flex items-center gap-3">
               <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center">
                  <Bot size={16} className="text-slate-500"/>
               </div>
               <div className="bg-slate-100 px-4 py-3 rounded-2xl rounded-tl-none border border-slate-200">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-75"></div>
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-150"></div>
                  </div>
               </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* --- ÁREA DE INPUT --- */}
      <div className="p-4 bg-white border-t border-slate-200 shadow-lg z-20">
        <div className="max-w-4xl mx-auto relative flex items-end gap-2 bg-slate-100 rounded-3xl p-2 border border-slate-300 focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-transparent">
          
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escribe tu consulta aquí..."
            className="w-full bg-transparent border-none focus:ring-0 resize-none max-h-32 min-h-[44px] py-3 px-4 text-slate-800 placeholder:text-slate-500 outline-none"
            rows={1}
            disabled={isLoading}
          />

          <button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isLoading}
            className={`flex-shrink-0 p-3 rounded-full mb-1 transition-all duration-200 ${
              !inputValue.trim() || isLoading
                ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700 shadow-md hover:scale-105 active:scale-95'
            }`}
          >
            {isLoading ? <Loader2 size={20} className="animate-spin" /> : <Send size={20} />}
          </button>
        </div>
        
        <div className="text-center mt-2">
            <p className="text-[10px] text-slate-400">
                MinCYT AI puede cometer errores. Verifica la información importante.
            </p>
        </div>
      </div>

    </div>
  );
};