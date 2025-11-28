import React, { useState, useEffect } from 'react';
import { ChatInterface } from './components/ChatInterface'; 
import { MeetingRecorder } from './components/MeetingRecorder';
import { MeetingHistory } from './components/MeetingHistory'; 
import { LayoutDashboard, RefreshCw, Eye, EyeOff, Bot, FileAudio } from 'lucide-react';

// URL del Backend
const API_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

function App() {
  const [data, setData] = useState([]);
  const [syncing, setSyncing] = useState(false);
  const [mostrarTabla, setMostrarTabla] = useState(true);
  const [activeTab, setActiveTab] = useState('recorder'); 

  const cargarDatos = () => {
    fetch(`${API_URL}/api/data`)
      .then(res => res.json())
      .then(datos => { if (Array.isArray(datos)) setData(datos); })
      .catch(console.error);
  };

  useEffect(() => { cargarDatos(); }, []);

  const sincronizar = async () => {
    setSyncing(true);
    await cargarDatos();
    setTimeout(() => { setSyncing(false); alert("Datos actualizados."); }, 800); 
  };

  const columnas = data.length > 0 ? Object.keys(data[0]) : [];

  return (
    <div className="max-w-[1600px] mx-auto p-4 md:p-8 min-h-screen">
      
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

      {/* --- SECCIÓN 1: TABLA DE DATOS (GLASS) --- */}
      {mostrarTabla && (
        <div className="bg-slate-900/40 backdrop-blur-md border border-white/10 rounded-2xl overflow-hidden mb-8 shadow-2xl">
          <div className="overflow-x-auto">
            {data.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                <p>Cargando datos del sistema...</p>
              </div>
            ) : (
              <table className="w-full text-sm text-left">
                <thead className="bg-white/5 text-slate-300 uppercase text-xs tracking-wider font-semibold">
                  <tr>
                    {columnas.map((col) => (
                      <th key={col} className="px-6 py-4 border-b border-white/5">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {data.slice(0, 8).map((row, i) => (
                    <tr key={i} className="hover:bg-white/[0.02] transition-colors group">
                      {columnas.map((col) => (
                        <td key={col} className="px-6 py-4 text-slate-400 whitespace-nowrap group-hover:text-slate-200 transition-colors">
                          {row[col] ? row[col].toString().substring(0, 50) + (row[col].toString().length > 50 ? '...' : '') : '-'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="bg-white/[0.02] px-6 py-2 border-t border-white/5 flex justify-between items-center">
             <p className="text-[10px] text-slate-500 uppercase tracking-widest">Vista Previa • Conexión Segura</p>
             {data.length > 8 && <span className="text-xs text-slate-500">Mostrando 8 de {data.length} registros</span>}
          </div>
        </div>
      )}
      
      {/* --- SECCIÓN 2: GRID DE HERRAMIENTAS IA --- */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-[750px]">
        
        {/* Columna Izquierda: CHATBOT */}
        <div className="rounded-2xl overflow-hidden shadow-2xl border border-white/10 bg-slate-900/60 backdrop-blur-xl flex flex-col">
            {/* Header Chat */}
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
            
            {/* Cuerpo Chat */}
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
                    <MeetingRecorder />
                ) : (
                    <div className="h-full p-6 overflow-y-auto custom-scrollbar">
                        <MeetingHistory />
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