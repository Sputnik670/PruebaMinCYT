import React, { useState, useRef } from 'react';
import { Mic, Square, Download, Trash2, FileText, Copy } from 'lucide-react';
import { sendAudioToGemini } from '../services/geminiService';

export const MeetingRecorder: React.FC = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcription, setTranscription] = useState('');
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  // --- Lógica de Grabación (Similar al Chat, pero acumulativa) ---
  const handleMicClick = async () => {
    if (isRecording) {
      stopRecording();
      return;
    }
    startRecording();
  };

  const startRecording = async () => {
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
        stream.getTracks().forEach(track => track.stop()); // Apagar mic
        await processAudio(audioBlob);
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Error mic:", err);
      alert("No se pudo acceder al micrófono.");
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  };

  const processAudio = async (audioBlob: Blob) => {
    setIsProcessing(true);
    try {
      // Llamamos al mismo servicio, pero el resultado lo guardamos en el estado local
      const text = await sendAudioToGemini(audioBlob);
      
      // ACUMULAMOS el texto (Append) en lugar de reemplazarlo
      setTranscription(prev => {
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        return prev + `\n[${time}] ${text}`;
      });

    } catch (error) {
      console.error("Error procesando reunión:", error);
      alert("Error al transcribir el audio. Revisa la consola.");
    } finally {
      setIsProcessing(false);
    }
  };

  // --- Funcionalidades de Archivo ---
  const handleDownload = () => {
    if (!transcription) return;
    const element = document.createElement("a");
    const file = new Blob([transcription], {type: 'text/plain'});
    element.href = URL.createObjectURL(file);
    element.download = `Reunion_${new Date().toISOString().slice(0,10)}.txt`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(transcription);
    alert("Texto copiado al portapapeles");
  };

  const handleClear = () => {
    if (window.confirm("¿Estás seguro de borrar toda la transcripción actual?")) {
      setTranscription('');
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      {/* Header de la herramienta */}
      <div className="bg-slate-100 p-4 border-b border-slate-200 flex justify-between items-center">
        <div className="flex items-center gap-2 text-slate-700">
            <FileText size={20} className="text-blue-600" />
            <h2 className="font-semibold">Actas de Reunión</h2>
        </div>
        {isProcessing && <span className="text-xs text-blue-500 animate-pulse">Procesando audio...</span>}
      </div>

      {/* Área de Texto (Editable) */}
      <textarea 
        className="flex-1 w-full p-4 resize-none focus:outline-none text-slate-700 font-mono text-sm bg-white"
        placeholder="Las transcripciones aparecerán aquí. Puedes editar este texto manualmente..."
        value={transcription}
        onChange={(e) => setTranscription(e.target.value)}
      />

      {/* Barra de Herramientas */}
      <div className="p-4 bg-slate-50 border-t border-slate-200 flex flex-wrap gap-3 items-center justify-between">
        
        {/* Botón Grabación */}
        <button
          onClick={handleMicClick}
          disabled={isProcessing}
          className={`flex items-center gap-2 px-6 py-3 rounded-full font-bold transition-all shadow-md ${
            isRecording 
              ? 'bg-red-500 hover:bg-red-600 text-white animate-pulse' 
              : 'bg-blue-600 hover:bg-blue-700 text-white'
          } ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          {isRecording ? <Square size={20} fill="currentColor" /> : <Mic size={20} />}
          {isRecording ? "Detener Grabación" : "Grabar Intervención"}
        </button>

        {/* Acciones Secundarias */}
        <div className="flex gap-2">
            <button 
                onClick={handleCopy} 
                disabled={!transcription}
                className="p-2 text-slate-600 hover:bg-slate-200 rounded-lg" 
                title="Copiar texto"
            >
                <Copy size={18} />
            </button>
            <button 
                onClick={handleDownload} 
                disabled={!transcription}
                className="p-2 text-green-600 hover:bg-green-100 rounded-lg" 
                title="Descargar archivo .txt"
            >
                <Download size={18} />
            </button>
            <button 
                onClick={handleClear} 
                disabled={!transcription}
                className="p-2 text-red-600 hover:bg-red-100 rounded-lg" 
                title="Borrar todo"
            >
                <Trash2 size={18} />
            </button>
        </div>
      </div>
    </div>
  );
};