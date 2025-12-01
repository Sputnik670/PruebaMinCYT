import React, { useState, useRef, useEffect } from 'react';
import { Message } from '../types/types';
import { sendMessageToGemini, uploadFile, sendAudioToGemini } from '../services/geminiService';
import { MessageBubble } from './MessageBubble';
import { Send, Loader2, Bot, Paperclip, FileText, Mic, Square, Trash2 } from 'lucide-react';

export const ChatInterface: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: '¡Hola! Soy Pitu, el asistente virtual del MinCYT. ¿En qué puedo ayudarte hoy? Puedes preguntarme sobre la agenda, subir un PDF o usar tu voz.',
      sender: 'bot',
      timestamp: new Date()
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  // Configuración robusta de la URL
  const rawUrl = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
  const API_URL = rawUrl.replace(/\/api\/?$/, "").replace(/\/$/, "");

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, isUploading]);

  // --- LÓGICA DE MEMORIA (PERSISTENCIA FORZADA) ---
  useEffect(() => {
    // 1. Intentamos recuperar una sesión existente
    let storedSession = localStorage.getItem('mincyt_chat_session_id');

    // 2. Si NO existe, creamos una "local" inmediatamente para no perder el primer mensaje
    if (!storedSession) {
        storedSession = 'local-' + Date.now().toString();
        localStorage.setItem('mincyt_chat_session_id', storedSession);
    }

    setSessionId(storedSession);

    // 3. Solo intentamos cargar historial si es una sesión real (no local nueva)
    // Esto evita llamadas 404 innecesarias al backend
    if (!storedSession.startsWith('local-')) {
        cargarHistorial(storedSession);
    }
  }, []);

  const cargarHistorial = async (id: string) => {
    try {
      const response = await fetch(`${API_URL}/api/sesiones/${id}/historial`);
      if (response.ok) {
        const data = await response.json();
        if (data.historial && data.historial.length > 0) {
          const historialFormateado: Message[] = [];
          
          data.historial.forEach((msg: any) => {
            if (msg.mensaje_usuario) {
              historialFormateado.push({
                id: `user-${msg.id}`,
                text: msg.mensaje_usuario,
                sender: 'user',
                timestamp: new Date(msg.timestamp)
              });
            }
            if (msg.respuesta_bot) {
              historialFormateado.push({
                id: `bot-${msg.id}`,
                text: msg.respuesta_bot,
                sender: 'bot',
                timestamp: new Date(msg.timestamp)
              });
            }
          });
          
          if (historialFormateado.length > 0) {
             setMessages(historialFormateado);
          }
        }
      }
    } catch (error) {
      console.error("Error cargando historial:", error);
    }
  };

  const limpiarSesion = () => {
    if(confirm("¿Deseas borrar el historial de esta conversación?")) {
        localStorage.removeItem('mincyt_chat_session_id');
        
        // Generamos una nueva limpia inmediatamente
        const newSession = 'local-' + Date.now().toString();
        localStorage.setItem('mincyt_chat_session_id', newSession);
        setSessionId(newSession);

        setMessages([{
            id: Date.now().toString(),
            text: 'Conversación reiniciada. ¿En qué puedo ayudarte ahora?',
            sender: 'bot',
            timestamp: new Date()
        }]);
    }
  };

  // --- LÓGICA DE AUDIO ---
  const handleMicClick = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      const chunks: BlobPart[] = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(chunks, { type: 'audio/webm' });
        stream.getTracks().forEach(track => track.stop());
        await sendAudioToBackend(audioBlob);
      };

      mediaRecorder.start();
      setIsRecording(true);

    } catch (err) {
      console.error("Error al acceder al micrófono:", err);
      alert("No se pudo acceder al micrófono. Verifica los permisos.");
    }
  };

  const sendAudioToBackend = async (audioBlob: Blob) => {
    setIsLoading(true);
    try {
      const text = await sendAudioToGemini(audioBlob);
      if (text) {
        setInputValue((prev) => (prev ? prev + ' ' : '') + text);
      }
    } catch (error) {
      console.error("Error enviando audio:", error);
      const errorMsg: Message = {
        id: Date.now().toString(),
        text: "❌ Error al procesar el audio. Asegúrate de que el backend esté corriendo.",
        sender: 'bot',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  // --- LÓGICA DE CHAT CON STREAMING ---
  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading || isUploading || isRecording) return;

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

    const botMsgId = (Date.now() + 1).toString();
    const botMessagePlaceholder: Message = {
      id: botMsgId,
      text: '',
      sender: 'bot',
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, botMessagePlaceholder]);

    try {
      // Enviamos el mensaje junto con el ID DE SESIÓN ACTUAL
      await sendMessageToGemini(
        userText, 
        messages, 
        (chunk) => {
            // Detector de cambio de sesión (cuando el backend confirma persistencia)
            if (chunk.includes("SESSION_ID:")) {
                const parts = chunk.split("SESSION_ID:");
                if (parts[1]) {
                    const newId = parts[1].trim();
                    console.log("Sesión persistida en backend:", newId);
                    setSessionId(newId);
                    localStorage.setItem('mincyt_chat_session_id', newId);
                }
                if (parts[0]) {
                    setMessages(prev => prev.map(msg => 
                        msg.id === botMsgId ? { ...msg, text: msg.text + parts[0] } : msg
                    ));
                }
            } else {
                setMessages(prev => prev.map(msg => 
                    msg.id === botMsgId ? { ...msg, text: msg.text + chunk } : msg
                ));
            }
        },
        sessionId // <--- AQUÍ ESTÁ LA CLAVE: Enviamos el ID al servicio
      );
      
    } catch (error) {
      console.error("Error:", error);
      setMessages(prev => prev.map(msg => {
            if (msg.id === botMsgId && msg.text === '') {
                return { ...msg, text: "⚠️ Lo siento, tuve un problema de conexión. Por favor intenta de nuevo." };
            }
            return msg;
        }));
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type !== 'application/pdf') {
        alert("Solo se permiten archivos PDF");
        return;
    }

    setIsUploading(true);
    
    const uploadingMsg: Message = {
        id: Date.now().toString(),
        text: `📎 Subiendo documento: ${file.name}...`,
        sender: 'user',
        timestamp: new Date(),
    };
    setMessages(prev => [...prev, uploadingMsg]);

    try {
        const respuestaServidor = await uploadFile(file);
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
    <div className="flex flex-col min-h-[600px] bg-slate-50 font-sans h-full">
      
      <header className="bg-[#002f6c] text-white p-4 shadow-md flex items-center justify-between">
        <div className="flex items-center gap-3">
            <div className="p-2 bg-white/10 rounded-full">
                <Bot size={24} />
            </div>
            <div>
                <h1 className="font-bold text-lg">MinCYT Asistente Virtual</h1>
                <p className="text-xs text-blue-200">Ministerio de Ciencia, Tecnología e Innovación</p>
            </div>
        </div>
        
        {/* Botón de Reiniciar Sesión */}
        {sessionId && (
            <button 
                onClick={limpiarSesion}
                className="text-white/70 hover:text-white text-xs flex items-center gap-1 bg-white/10 px-2 py-1 rounded transition-colors"
                title="Borrar historial y empezar de nuevo"
            >
                <Trash2 size={12}/> Reiniciar
            </button>
        )}
      </header>

      <div className="flex-1 max-h-[calc(100vh-200px)] overflow-y-auto p-4 md:p-8 w-full max-w-4xl mx-auto scrollbar-hide">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {(isLoading && messages[messages.length - 1]?.sender !== 'bot') && (
          <div className="flex justify-start w-full mb-6 animate-pulse">
            <div className="flex items-center gap-3">
               <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center">
                  <Bot size={16} className="text-slate-500"/>
               </div>
               <div className="bg-slate-100 px-4 py-3 rounded-2xl rounded-tl-none border border-slate-200 flex items-center gap-2">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-75"></div>
                    <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-150"></div>
                  </div>
               </div>
            </div>
          </div>
        )}
        
        {isUploading && (
             <div className="flex justify-start w-full mb-6 animate-pulse">
             <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center">
                   <Bot size={16} className="text-slate-500"/>
                </div>
                <div className="bg-slate-100 px-4 py-3 rounded-2xl rounded-tl-none border border-slate-200 flex items-center gap-2">
                   <FileText size={16} className="text-slate-500" />
                   <span className="text-xs text-slate-500">Leyendo documento...</span>
                </div>
             </div>
           </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 bg-white border-t border-slate-200 shadow-lg z-20">
        <div className="max-w-4xl mx-auto relative flex items-end gap-2 bg-slate-100 rounded-3xl p-2 border border-slate-300 focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-transparent">
          
          <input 
            type="file" 
            accept="application/pdf" 
            ref={fileInputRef} 
            onChange={handleFileChange} 
            className="hidden" 
            aria-label="Subir documento PDF" 
          />
          <button
            onClick={handleFileClick}
            disabled={isLoading || isUploading || isRecording}
            className="flex-shrink-0 p-3 rounded-full mb-1 text-slate-500 hover:bg-slate-200 transition-colors"
            title="Adjuntar PDF"
          >
            <Paperclip size={20} />
          </button>

          <button
            onClick={handleMicClick}
            disabled={isLoading || isUploading}
            className={`flex-shrink-0 p-3 rounded-full mb-1 transition-all duration-300 ${
              isRecording 
                ? 'bg-red-500 text-white animate-pulse shadow-red-300 shadow-md' 
                : 'text-slate-500 hover:bg-slate-200'
            }`}
            title={isRecording ? "Detener grabación" : "Grabar mensaje de voz"}
          >
            {isRecording ? <Square size={20} fill="currentColor" /> : <Mic size={20} />}
          </button>

          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isRecording ? "Escuchando..." : "Escribe tu consulta..."}
            className="w-full bg-transparent border-none focus:ring-0 resize-none max-h-32 min-h-[44px] py-3 px-2 text-slate-800 placeholder:text-slate-500 outline-none"
            rows={1}
            disabled={isLoading || isUploading}
          />

          <button
            onClick={handleSendMessage}
            disabled={!inputValue.trim() || isLoading || isUploading || isRecording}
            className={`flex-shrink-0 p-3 rounded-full mb-1 transition-all duration-200 ${
              !inputValue.trim() || isLoading || isUploading || isRecording
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