import React, { useState, useRef } from 'react';
import { Mic, Square, Download, Trash2, Copy, Loader2, Wand2 } from 'lucide-react';
import { sendAudioToGemini } from '../services/geminiService';

export const MeetingRecorder: React.FC = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcription, setTranscription] = useState('');
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  // Lógica de Grabación
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

      mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(chunks, { type: 'audio/webm' });
        stream.getTracks().forEach(track => track.stop());
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
      const text = await sendAudioToGemini(audioBlob);
      setTranscription(prev => {
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        return prev + (prev ? '\n\n' : '') + `[${time}] ${text}`;
      });
    } catch (error) {
      console.error("Error procesando reunión:", error);
      alert("Error al transcribir. Ver consola.");
    } finally {
      setIsProcessing(false);
    }
  };

  // Helpers de UI
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
  };

  const handleClear = () => {
    if (window.confirm("¿Borrar acta actual?")) setTranscription('');
  };

  return (
    <div className="flex flex-col h-full bg-transparent relative">
      
      {/* Header Interno */}
      <div className="p-6 pb-4 flex justify-between items-end z-10">
        <div>
            <h2 className="text-lg font-medium text-white flex items-center gap-2">
                <Wand2 size={16} className="text-purple-400"/> Transcripción Inteligente
            </h2>
            <p className="text-xs text-slate-400 mt-1">Gemini escuchará y redactará el acta automáticamente.</p>
        </div>
        {isProcessing && (
            <div className="flex items-center gap-2 text-blue-400 text-xs bg-blue-500/10 px-3 py-1.5 rounded-full border border-blue-500/20 animate-pulse">
                <Loader2 size={12} className="animate-spin"/> Procesando audio...
            </div>
        )}
      </div>

      {/* Área de Texto Estilizada */}
      <div className="flex-1 px-6 pb-24 overflow-hidden">
         <div className="h-full w-full bg-black/20 border border-white/5 rounded-xl relative group transition-all hover:border-white/10 hover:bg-black/30">
            <textarea 
                className="w-full h-full bg-transparent p-6 text-slate-300 placeholder:text-slate-600 focus:ring-0 border-none outline-none resize-none font-mono text-sm leading-relaxed scrollbar-hide"
                placeholder="Presiona 'Grabar' para comenzar la reunión..."
                value={transcription}
                onChange={(e) => setTranscription(e.target.value)}
            />
         </div>
      </div>

      {/* Barra de Herramientas Flotante */}
      <div className="absolute bottom-6 left-6 right-6 h-20 z-20">
        <div className="h-full bg-slate-900/80 backdrop-blur-md border border-white/10 rounded-2xl p-4 flex items-center justify-between gap-4 shadow-xl">
            
            <button
                onClick={handleMicClick}
                disabled={isProcessing}
                className={`flex items-center gap-3 px-6 py-3 rounded-xl font-semibold transition-all duration-300 shadow-lg min-w-[140px] justify-center ${
                    isRecording 
                    ? 'bg-red-500/90 hover:bg-red-600 text-white shadow-red-500/20 animate-pulse' 
                    : 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/20 hover:scale-105'
                } ${isProcessing ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
                {isRecording ? <Square size={18} fill="currentColor" /> : <Mic size={18} />}
                <span className="tracking-wide text-sm">{isRecording ? "DETENER" : "GRABAR"}</span>
            </button>

            <div className="flex gap-1 border-l border-white/10 pl-4">
                <button onClick={handleCopy} disabled={!transcription} className="p-3 text-slate-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors" title="Copiar">
                    <Copy size={18} />
                </button>
                <button onClick={handleDownload} disabled={!transcription} className="p-3 text-slate-400 hover:text-emerald-400 hover:bg-emerald-500/10 rounded-lg transition-colors" title="Descargar">
                    <Download size={18} />
                </button>
                <button onClick={handleClear} disabled={!transcription} className="p-3 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors" title="Limpiar">
                    <Trash2 size={18} />
                </button>
            </div>
        </div>
      </div>
    </div>
  );
};