import { useState, useEffect } from 'react';
import './App.css';
import { ChatInterface } from './components/ChatInterface'; 
import { MeetingRecorder } from './components/MeetingRecorder';
import { MeetingHistory } from './components/MeetingHistory'; 
import { LayoutDashboard, RefreshCw, Eye, EyeOff, Bot, FileAudio, Building2, Briefcase } from 'lucide-react';
import { AgendaItem } from './types/types'; // Importamos el tipo actualizado

// Configuración de red
const rawUrl = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
const API_URL = rawUrl.replace(/\/api\/?$/, "").replace(/\/$/, "");

type VistaType = 'cliente' | 'ministerio';
type TabType = 'recorder' | 'history';

function App() {
  const [dataMinisterio, setDataMinisterio] = useState<AgendaItem[]>([]);
  const [dataCliente, setDataCliente] = useState<AgendaItem[]>([]);
  
  const [vistaActual, setVistaActual] = useState<VistaType>('cliente'); 
  const [syncing, setSyncing] = useState(false);
  const [mostrarTabla, setMostrarTabla] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('recorder'); 
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleUploadSuccess = () => {
    setRefreshTrigger(prev => prev + 1);
    setActiveTab('history');
  };

  const cargarDatos = async () => {
    try {
        const [resMin, resCli] = await Promise.all([
            fetch(`${API_URL}/api/agenda/ministerio`),
            fetch(`${API_URL}/api/agenda/cliente`)
        ]);
        
        const jsonMin = await resMin.json();
        const jsonCli = await resCli.json();

        if (Array.isArray(jsonMin)) setDataMinisterio(jsonMin);
        if (Array.isArray(jsonCli)) setDataCliente(jsonCli);

    } catch (error) {
        console.error("Error cargando agendas:", error);
    }
  };

  useEffect(() => { cargarDatos(); }, []);

  const sincronizar = async () => {
    setSyncing(true);
    await cargarDatos();
    setRefreshTrigger(prev => prev + 1);
    setTimeout(() => setSyncing(false), 800); 
  };

  const datosVisibles = vistaActual === 'cliente' ? dataCliente : dataMinisterio;

  // --- CONFIGURACIÓN DE COLUMNAS ACTUALIZADA ---
  const columnConfig: Record<string, string> = {
    fecha: "📅 Fecha",
    titulo: "📌 Evento / Motivo",
    lugar: "📍 Ubicación",
    funcionario: "👤 Funcionario",
    costo: "💰 Costo",  // <--- AHORA USAMOS 'COSTO' GENÉRICO
    ambito: "🌍 Ámbito",
    estado: "📊 Estado",
    num_expediente: "📂 Exp.",
    organizador: "🏢 Organiza"
  };

  // Renderizado Inteligente de Celdas
  const renderCell = (key: string, value: any, item: AgendaItem) => {
    if (!value && value !== 0) return <span className="text-slate-300">-</span>;
    
    // LÓGICA MULTIMONEDA
    if (key === 'costo' && typeof value === 'number') {
        const moneda = item.moneda || 'ARS';
        let colorClass = 'text-emerald-600'; // Default ARS
        
        if (moneda === 'USD') colorClass = 'text-green-400';
        if (moneda === 'EUR') colorClass = 'text-blue-400';

        return (
            <div className="flex flex-col">
                <span className={`font-mono font-bold ${colorClass}`}>
                    {new Intl.NumberFormat('es-AR', { style: 'currency', currency: moneda }).format(value)}
                </span>
                {/* Pequeña etiqueta de moneda si no es ARS */}
                {moneda !== 'ARS' && <span className="text-[10px] text-slate-500">{moneda}</span>}
            </div>
        );
    }

    if (key === 'fecha') {
        return new Date(value).toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' });
    }

    if (key === 'ambito') {
        const color = value === 'Internacional' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700';
        return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>{value}</span>;
    }

    return String(value).substring(0, 60);
  };

  // Columnas a mostrar (Usamos 'costo' en vez de 'costo_ars')
  const columnasMostrar = vistaActual === 'cliente' 
    ? ['fecha', 'titulo', 'funcionario', 'lugar', 'costo', 'estado']
    : ['fecha', 'titulo', 'organizador', 'lugar', 'ambito'];

  return (
    <div className="max-w-[1600px] mx-auto p-4 md:p-8 min-h-screen text-slate-300">
      
      {/* HEADER */}
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
            className="flex items-center gap-2 px-4 py-2 bg-slate-800/50 hover:bg-slate-800 border border-white/10 rounded-lg transition-all text-slate-300 text-sm font-medium"
          >
            {mostrarTabla ? <><EyeOff size={16}/> Ocultar</> : <><Eye size={16}/> Ver Datos</>}
          </button>
          <button 
            onClick={sincronizar} 
            disabled={syncing} 
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-all shadow-lg shadow-blue-900/20 text-sm font-medium disabled:opacity-50 border border-blue-500/50"
          >
            <RefreshCw size={16} className={syncing ? "animate-spin" : ""} />
            {syncing ? 'Sincronizando...' : 'Actualizar'}
          </button>
        </div>
      </header>

      {/* CONTROLES */}
      {mostrarTabla && (
        <div className="flex gap-4 mb-4">
            <button 
                onClick={() => setVistaActual('cliente')}
                className={`flex items-center gap-2 px-6 py-3 rounded-xl border transition-all ${
                    vistaActual === 'cliente' 
                    ? 'bg-blue-600/20 border-blue-500 text-blue-400 shadow-lg shadow-blue-900/20' 
                    : 'bg-slate-900/40 border-white/5 text-slate-500 hover:bg-slate-800 hover:text-slate-300'
                }`}
            >
                <Briefcase size={18} />
                <span className="font-semibold">Gestión Interna</span>
                <span className="ml-2 bg-black/20 px-2 py-0.5 rounded text-xs">{dataCliente.length}</span>
            </button>

            <button 
                onClick={() => setVistaActual('ministerio')}
                className={`flex items-center gap-2 px-6 py-3 rounded-xl border transition-all ${
                    vistaActual === 'ministerio' 
                    ? 'bg-purple-600/20 border-purple-500 text-purple-400 shadow-lg shadow-purple-900/20' 
                    : 'bg-slate-900/40 border-white/5 text-slate-500 hover:bg-slate-800 hover:text-slate-300'
                }`}
            >
                <Building2 size={18} />
                <span className="font-semibold">Agenda Oficial</span>
                <span className="ml-2 bg-black/20 px-2 py-0.5 rounded text-xs">{dataMinisterio.length}</span>
            </button>
        </div>
      )}

      {/* TABLA */}
      {mostrarTabla && (
        <div className="bg-white text-slate-900 rounded-2xl overflow-hidden mb-8 shadow-xl border border-slate-200 transition-all duration-300">
          <div className="overflow-x-auto max-h-[500px] custom-scrollbar"> 
            {datosVisibles.length === 0 ? (
              <div className="p-12 text-center text-slate-500">
                <p>Base de datos sincronizada. No hay registros para esta vista.</p>
              </div>
            ) : (
              <table className="w-full text-sm text-left relative">
                <thead className="bg-slate-100 text-slate-900 uppercase text-xs tracking-wider font-bold border-b border-slate-300 sticky top-0 z-10 shadow-sm">
                  <tr>
                    {columnasMostrar.map((colKey) => (
                      <th key={colKey} className="px-6 py-4 whitespace-nowrap">
                        {columnConfig[colKey] || colKey}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {datosVisibles.map((row, i) => (
                    <tr key={i} className="hover:bg-slate-50 transition-colors group">
                      {columnasMostrar.map((colKey) => (
                        <td key={colKey} className="px-6 py-4 whitespace-nowrap text-slate-700 font-medium">
                          {/* @ts-ignore */}
                          {renderCell(colKey, row[colKey as keyof AgendaItem], row)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="bg-slate-50 px-6 py-3 border-t border-slate-200 flex justify-between items-center text-xs text-slate-500 font-medium">
             <p className="uppercase tracking-widest">
                {vistaActual === 'cliente' ? '📁 Fuente: SQL Misiones' : '🏛️ Fuente: SQL Público'}
             </p>
             <span>Sincronizado: {new Date().toLocaleTimeString()}</span>
          </div>
        </div>
      )}
      
      {/* SECCIÓN 2: HERRAMIENTAS IA */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-[750px]">
        <div className="rounded-2xl overflow-hidden shadow-2xl border border-white/10 bg-slate-900/60 backdrop-blur-xl flex flex-col">
            <div className="bg-white/5 p-4 border-b border-white/5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-500/20 rounded-lg text-blue-400 border border-blue-500/30">
                        <Bot size={20} />
                    </div>
                    <div>
                        <h2 className="text-sm font-semibold text-slate-100">Asistente MinCYT</h2>
                        <p className="text-xs text-blue-400">En línea • Gemini 1.5 Flash</p>
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

        <div className="rounded-2xl overflow-hidden shadow-2xl border border-white/10 bg-slate-900/60 backdrop-blur-xl flex flex-col">
            <div className="flex border-b border-white/10 bg-black/20">
                <button 
                    onClick={() => setActiveTab('recorder')}
                    className={`flex-1 py-4 text-sm font-medium transition-all relative flex justify-center items-center gap-2 ${
                        activeTab === 'recorder' ? 'text-blue-400 bg-white/5' : 'text-slate-500 hover:text-slate-300'
                    }`}
                >
                    <div className={`w-2 h-2 rounded-full ${activeTab === 'recorder' ? 'bg-red-500 animate-pulse' : 'bg-slate-600'}`}></div>
                    Sala de Grabación
                </button>
                <button 
                    onClick={() => setActiveTab('history')}
                    className={`flex-1 py-4 text-sm font-medium transition-all relative flex justify-center items-center gap-2 ${
                        activeTab === 'history' ? 'text-blue-400 bg-white/5' : 'text-slate-500 hover:text-slate-300'
                    }`}
                >
                    <FileAudio size={14} />
                    Archivo de Actas
                </button>
            </div>
            <div className="flex-1 p-0 relative overflow-hidden bg-transparent">
                {activeTab === 'recorder' ? (
                    <MeetingRecorder onUploadSuccess={handleUploadSuccess} />
                ) : (
                    <div className="h-full p-6 overflow-y-auto custom-scrollbar">
                        <MeetingHistory refreshTrigger={refreshTrigger} />
                    </div>
                )}
            </div>
        </div>
      </div>
      
      <footer className="mt-12 mb-6 text-center">
        <p className="text-xs text-slate-600 font-mono">MINCYT AI SYSTEM v3.2 • MULTIMONEDA ACTIVE</p>
      </footer>
    </div>
  );
}

export default App;