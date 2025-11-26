import React, { useState, useRef, useEffect } from 'react';
import { Message } from '../types/types';
import { sendMessageToGemini, uploadFile } from '../services/geminiService'; // <--- Importamos uploadFile
import { MessageBubble } from './MessageBubble';
import { Send, Loader2, Bot, Paperclip, FileText } from 'lucide-react'; // <--- Importamos Paperclip y FileText

export const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: '¡Hola! Soy el asistente virtual del MinCYT. ¿En qué puedo ayudarte hoy? Puedes preguntarme sobre la agenda o subir un PDF para que lo analice.',
      sender: 'bot',
      timestamp: new Date()
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false); // Estado para la subida de archivo
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null); // Referencia al input oculto

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, isUploading]);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading || isUploading) return;

    const userText = inputValue.trim();
    setInputValue('');

    const userMessage: Message = {
      id: Date.now().toString(),
      text: userText,
      sender: 'user',
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const responseText = await sendMessageToGemini(userText);
      
      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: responseText,
        sender: 'bot',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error("Error:", error);
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

  // Manejar clic en el clip
  const handleFileClick = () => {
    fileInputRef.current?.click();
  };

  // Manejar selección de archivo
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type !== 'application/pdf') {
        alert("Solo se permiten archivos PDF");
        return;
    }

    setIsUploading(true);
    
    // Mensaje visual de "Subiendo..."
    const uploadingMsg: Message = {
        id: Date.now().toString(),
        text: `📎 Subiendo documento: ${file.name}...`,
        sender: 'user',
        timestamp: new Date(),
    };
    setMessages(prev => [...prev, uploadingMsg]);

    try {
        // 1. Subir al backend
        const respuestaServidor = await uploadFile(file);

        // 2. Respuesta del bot confirmando lectura
        const botConfirm: Message = {
            id: (Date.now() + 1).toString(),
            text: `✅ ${respuestaServidor} Ahora puedes hacerme preguntas sobre el documento.`,
            sender: 'bot',
            timestamp: new Date(),
        };
        setMessages(prev => [...prev, botConfirm]);

    } catch (error) {
        const errorMsg: Message = {
            id: (Date.now() + 1).toString(),
            text: `❌ Error al subir el archivo: ${error instanceof Error ? error.message : 'Error desconocido'}`,
            sender: 'bot',
            timestamp: new Date(),
        };
        setMessages(prev => [...prev, errorMsg]);
    } finally {
        setIsUploading(false);
        // Limpiar el input para permitir subir el mismo archivo de nuevo si falla
        if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex flex-col min-h-[600px] bg-slate-50 font-sans">
      
      <header className="bg-[#002f6c] text-white p-4 shadow-md flex items-center gap-3">
        <div className="p-2 bg-white/10 rounded-full">
            <Bot size={24} />
        </div>
        <div>
            <h1 className="font-bold text-lg">MinCYT Asistente Virtual</h1>
            <p className="text-xs text-blue-200">Ministerio de Ciencia, Tecnología e Innovación</p>
        </div>
      </header>

      <div className="flex-1 max-h-[calc(100vh - 200px)] overflow-y-auto p-4 md:p-8 w-full max-w-4xl mx-auto scrollbar-hide">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {(isLoading || isUploading) && (
          <div className="flex justify-start w-full mb-6 animate-pulse">
            <div className="flex items-center gap-3">
               <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center">
                  <Bot size={16} className="text-slate-500"/>
               </div>
               <div className="bg-slate-100 px-4 py-3 rounded-2xl rounded-tl-none border border-slate-200 flex items-center gap-2">
                  {isUploading ? (
                      <>
                        <FileText size={16} className="text-slate-500" />
                        <span className="text-xs text-slate-500">Leyendo documento...</span>
                      </>
                  ) : (
                      <div className="flex space-x-1">
                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-75"></div>
                        <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-150"></div>
                      </div>
                  )}
               </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 bg-white border-t border-slate-200 shadow-lg z-20">
        <div className="max-w-4xl mx-auto relative flex items-end gap-2 bg-slate-100 rounded-3xl p-2 border border-slate-300 focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-transparent">
          
          {/* --- BOTÓN DE ADJUNTAR (NUEVO) --- */}
          <input 
            type="file" 
            accept="application/pdf" 
            ref={fileInputRef} 
            onChange={handleFileChange} 
            className="hidden" 
            aria-label="Subir documento PDF" // <--- SOLUCIÓN AÑADIDA
          />
          <button
            onClick={handleFileClick}
            disabled={isLoading || isUploading}
            className="flex-shrink-0 p-3 rounded-full mb-1 text-slate-500 hover:bg-slate-200 transition-colors"
            title="Adjuntar PDF"
          >
            <Paperclip size={20} />
          </button>

          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escribe tu consulta..."
            className="w-full bg-transparent border-none focus:ring-0 resize-none max-h-32 min-h-[44px] py-3 px-2 text-slate-800 placeholder:text-slate-500 outline-none"
            rows={1}
            disabled={isLoading || isUploading}
          />

          <button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isLoading || isUploading}
            className={`flex-shrink-0 p-3 rounded-full mb-1 transition-all duration-200 ${
              !inputValue.trim() || isLoading || isUploading
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