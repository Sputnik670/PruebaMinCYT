import { useState, useRef } from 'react';
import { Mic, Square, Loader2, FileText } from 'lucide-react';
import { sendAudioToGemini } from '../services/geminiService';

// Definimos que este componente puede recibir una función opcional
export const MeetingRecorder = ({ onUploadSuccess }: { onUploadSuccess?: () => void }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcript, setTranscript] = useState<string | null>(null);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' });
        await handleAudioUpload(audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      setTranscript(null);
    } catch (err) {
      console.error("Error accediendo al micrófono:", err);
      alert("No se pudo acceder al micrófono. Verifique los permisos.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      setIsProcessing(true);
    }
  };

  const handleAudioUpload = async (audioBlob: Blob) => {
    try {
      const text = await sendAudioToGemini(audioBlob);
      setTranscript(text);
      
      // ¡AQUÍ ESTÁ EL CAMBIO! Avisamos al padre (App.jsx) que terminamos
      if (onUploadSuccess) {
        onUploadSuccess();
      }

    } catch (error) {
      console.error(error);
      alert("Error procesando el audio. Intente nuevamente.");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className={`p-4 rounded-full transition-all duration-500 ${isRecording ? 'bg-red-100 animate-pulse' : 'bg-blue-50'}`}>
          <Mic className={`w-8 h-8 ${isRecording ? 'text-red-500' : 'text-blue-600'}`} />
        </div>
        
        <div>
          <h3 className="font-semibold text-slate-900">Grabar Reunión</h3>
          <p className="text-sm text-slate-500 mt-1">
            {isRecording 
              ? "Grabando... (Haga click en parar para finalizar)" 
              : "El asistente transcribirá y analizará la reunión."} 
          </p>
        </div>

        {!isRecording ? (
          <button
            onClick={startRecording}
            disabled={isProcessing}
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isProcessing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Procesando...
              </>
            ) : (
              <>
                <Mic className="w-4 h-4" />
                Iniciar Grabación
              </>
            )}
          </button>
        ) : (
          <button
            onClick={stopRecording}
            className="px-6 py-2.5 bg-red-500 hover:bg-red-600 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
          >
            <Square className="w-4 h-4 fill-current" />
            Detener y Procesar
          </button>
        )}

        {transcript && (
          <div className="w-full mt-4 p-4 bg-slate-50 rounded-lg border border-slate-200 text-left">
            <div className="flex items-center gap-2 mb-2 text-slate-800 font-medium">
              <FileText className="w-4 h-4 text-green-600" />
              Transcripción Generada:
            </div>
            <p className="text-slate-700 text-sm leading-relaxed whitespace-pre-wrap">
              {transcript}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};