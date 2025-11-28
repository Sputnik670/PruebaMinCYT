import { useState, useEffect } from 'react';
import './App.css';
// --- COMPONENTS ---
import { ChatInterface } from './components/ChatInterface'; 
import { MeetingRecorder } from './components/MeetingRecorder';
import { MeetingHistory } from './components/MeetingHistory'; 
import { LayoutDashboard, RefreshCw, Eye, EyeOff, Bot, FileAudio } from 'lucide-react';

// --- CONFIGURACIÓN ROBUSTA DEL BACKEND ---
const rawUrl = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const API_URL = rawUrl.replace(/\/api\/?$/, "").replace(/\/$/, "");

console.log("Conectando a:", API_URL); 

function App() {
  const [data, setData] = useState([]);
  const [syncing, setSyncing] = useState(false);
  const [mostrarTabla, setMostrarTabla] = useState(true);
  const [activeTab, setActiveTab] = useState('recorder'); 

  // --- NUEVO: Estado para forzar la recarga del historial ---
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // --- NUEVO: Función que llama el Recorder cuando termina ---
  const handleUploadSuccess = () => {
    console.log("Audio subido con éxito, actualizando historial...");
    setRefreshTrigger(prev => prev + 1);
    setActiveTab('history'); // Opcional: Cambiar a la pestaña de historial automáticamente
  };

  const cargarDatos = () => {
    fetch(`${API_URL}/api/data`)
      .then(res => res.json())
      .then(datos => { if (Array.isArray(datos)) setData(datos); })
      .catch(error => console.error("Error conectando al backend:", error));
  };

  useEffect(() => { cargarDatos(); }, []);

  const sincronizar = async () => {
    setSyncing(true);
    await cargarDatos();
    // También actualizamos el historial manual
    setRefreshTrigger(prev => prev + 1);
    setTimeout(() => { setSyncing(false); alert("Datos actualizados."); }, 800); 
  };

  const columnas = data.length > 0 ? Object.keys(data[0]) : [];

  return (
    <div className="max-w-[1600px] mx-auto p-4 md:p-8 min-h-screen text-slate-300">
      
      {/* --- HEADER --- */}
      <header className="flex flex-col md:flex-row justify-between items-end mb-8 pb-6 border-b border-white/10 gap-4">
        <div className="w-full md:w-auto">
          <h1 className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent flex items-center gap-3">
            <LayoutDashboard className="text-blue-400" size={32} /> 
            MinCYT Dashboard
          </h1>
          <p className="text-slate-400 text-sm mt-2 ml-1">Plataforma de Gestión Inteligente & IA</p>
        </div>
        
        <div className="flex gap-3">
          <button 
            onClick={() => setMostrarTabla(!mostrarTabla)} 
            className="flex items-center gap-2 px-4 py-2 bg-slate-800/50 hover:bg-slate-800 border border-white/10 rounded-lg transition-all text-slate-300 text-sm font-medium backdrop-blur-sm"
          >
            {mostrarTabla ? <><EyeOff size={16}/> Ocultar</> : <><Eye size={16}/> Ver Datos</>}
          </button>
          <button 
            onClick={sincronizar} 
            disabled={syncing} 
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-all shadow-lg shadow-blue-900/20 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed border border-blue-500/50"
          >
            <RefreshCw size={16} className={syncing ? "animate-spin" : ""} />
            {syncing ? 'Sincronizando...' : 'Actualizar'}
          </button>
        </div>
      </header>

      {/* --- SECCIÓN 1: TABLA DE DATOS --- */}
      {mostrarTabla && (
        <div className="bg-white text-slate-900 rounded-2xl overflow-hidden mb-8 shadow-xl border border-slate-200">
          <div className="overflow-x-auto">
            {data.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                <p>Esperando conexión con el servidor...</p>
              </div>
            ) : (
              <table className="w-full text-sm text-left">
                <thead className="bg-slate-100 text-slate-900 uppercase text-xs tracking-wider font-bold border-b border-slate-300">
                  <tr>
                    {columnas.map((col) => (
                      <th key={col} className="px-6 py-4">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {data.slice(0, 8).map((row, i) => (
                    <tr key={i} className="hover:bg-slate-50 transition-colors">
                      {columnas.map((col) => (
                        <td key={col} className="px-6 py-4 whitespace-nowrap text-slate-700 font-medium">
                          {row[col] ? row[col].toString().substring(0, 50) + (row[col].toString().length > 50 ? '...' : '') : '-'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="bg-slate-50 px-6 py-2 border-t border-slate-200 flex justify-between items-center text-slate-500">
             <p className="text-[10px] uppercase tracking-widest font-semibold">Vista Previa • Datos en vivo</p>
             {data.length > 8 && <span className="text-xs">Mostrando 8 de {data.length} registros</span>}
          </div>
        </div>
      )}
      
      {/* --- SECCIÓN 2: GRID DE HERRAMIENTAS IA --- */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-[750px]">
        
        {/* Columna Izquierda: CHATBOT */}
        <div className="rounded-2xl overflow-hidden shadow-2xl border border-white/10 bg-slate-900/60 backdrop-blur-xl flex flex-col">
            <div className="bg-white/5 p-4 border-b border-white/5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-500/20 rounded-lg text-blue-400 border border-blue-500/30">
                        <Bot size={20} />
                    </div>
                    <div>
                        <h2 className="text-sm font-semibold text-slate-100">Asistente MinCYT</h2>
                        <p className="text-xs text-blue-400">En línea • Gemini 2.5 Flash</p>
                    </div>
                </div>
                <div className="flex space-x-1">
                   <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"></div>
                </div>
            </div>
            
            <div className="flex-1 overflow-hidden relative bg-transparent">
                <ChatInterface /> 
            </div>
        </div>

        {/* Columna Derecha: REUNIONES & ACTAS */}
        <div className="rounded-2xl overflow-hidden shadow-2xl border border-white/10 bg-slate-900/60 backdrop-blur-xl flex flex-col">
            {/* Tabs de Navegación */}
            <div className="flex border-b border-white/10 bg-black/20">
                <button 
                    onClick={() => setActiveTab('recorder')}
                    className={`flex-1 py-4 text-sm font-medium transition-all relative flex justify-center items-center gap-2 ${
                        activeTab === 'recorder' 
                        ? 'text-blue-400 bg-white/5' 
                        : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]'
                    }`}
                >
                    <div className={`w-2 h-2 rounded-full ${activeTab === 'recorder' ? 'bg-red-500 animate-pulse' : 'bg-slate-600'}`}></div>
                    Sala de Grabación
                    {activeTab === 'recorder' && <div className="absolute bottom-0 left-0 w-full h-[2px] bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]"></div>}
                </button>
                <button 
                    onClick={() => setActiveTab('history')}
                    className={`flex-1 py-4 text-sm font-medium transition-all relative flex justify-center items-center gap-2 ${
                        activeTab === 'history' 
                        ? 'text-blue-400 bg-white/5' 
                        : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.02]'
                    }`}
                >
                    <FileAudio size={14} />
                    Archivo de Actas
                    {activeTab === 'history' && <div className="absolute bottom-0 left-0 w-full h-[2px] bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,0.5)]"></div>}
                </button>
            </div>

            {/* Contenido Dinámico */}
            <div className="flex-1 p-0 relative overflow-hidden bg-transparent">
                {activeTab === 'recorder' ? (
                    // Pasamos la función handleUploadSuccess al Recorder
                    <MeetingRecorder onUploadSuccess={handleUploadSuccess} />
                ) : (
                    <div className="h-full p-6 overflow-y-auto custom-scrollbar">
                        {/* Pasamos el refreshTrigger al History */}
                        <MeetingHistory refreshTrigger={refreshTrigger} />
                    </div>
                )}
            </div>
        </div>
      </div>
      
      <footer className="mt-12 mb-6 text-center">
        <p className="text-xs text-slate-600 font-mono">MINCYT AI SYSTEM v2.0.5 • SECURE CONNECTION ESTABLISHED</p>
      </footer>

    </div>
  );
}

export default App;