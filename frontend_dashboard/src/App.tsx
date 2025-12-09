import { useState, useEffect } from 'react';
import './App.css';
import { supabase } from './supabaseClient';
import { Session } from '@supabase/supabase-js';
import { ChatInterface } from './components/ChatInterface'; 
import { MeetingRecorder } from './components/MeetingRecorder';
import { MeetingHistory } from './components/MeetingHistory'; 
import { EventModal } from './components/EventModal'; // <--- 1. IMPORTAR EL MODAL
import { LayoutDashboard, RefreshCw, Eye, EyeOff, Bot, FileAudio, Building2, Briefcase, LogOut, Lock } from 'lucide-react';
import { AgendaItem } from './types/types'; 

// Configuración de red
const rawUrl = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
const API_URL = rawUrl.replace(/\/api\/?$/, "").replace(/\/$/, "");

type VistaType = 'cliente' | 'ministerio';
type TabType = 'recorder' | 'history';

function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loadingAuth, setLoadingAuth] = useState(true);

  // --- ESTADO DEL DASHBOARD ---
  const [dataMinisterio, setDataMinisterio] = useState<AgendaItem[]>([]);
  const [dataCliente, setDataCliente] = useState<AgendaItem[]>([]);
  const [vistaActual, setVistaActual] = useState<VistaType>('cliente'); 
  const [syncing, setSyncing] = useState(false);
  const [mostrarTabla, setMostrarTabla] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('recorder'); 
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // --- 2. ESTADOS PARA EL MODAL DE DETALLES ---
  const [selectedEvent, setSelectedEvent] = useState<AgendaItem | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // 1. EFECTO PARA VERIFICAR SESIÓN AL INICIAR
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setLoadingAuth(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  // 2. FUNCIÓN DE LOGIN CON GOOGLE
  const handleGoogleLogin = async () => {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: window.location.origin, 
      },
    });
  };

  // 3. FUNCIÓN DE LOGOUT
  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  const handleUploadSuccess = () => {
    setRefreshTrigger(prev => prev + 1);
    setActiveTab('history');
  };

  // --- 3. MANEJADOR DE CLIC EN FILA ---
  const handleRowClick = (item: AgendaItem) => {
    setSelectedEvent(item);
    setIsModalOpen(true);
  };

  const cargarDatos = async () => {
    try {
      console.log("🔄 Cargando datos desde Supabase (agenda_unificada)...");
      
      // 1. Cargar "Agenda Oficial" (Filtramos por ámbito Público/Oficial)
      const { data: oficialData, error: errorOficial } = await supabase
        .from('agenda_unificada')
        .select('*')
        .in('ambito', ['Oficial', 'Internacional', 'Nacional'])
        .order('fecha', { ascending: true });

      if (errorOficial) throw errorOficial;

      // 2. Cargar "Gestión Interna" (Todo lo demás)
      const { data: gestionData, error: errorGestion } = await supabase
        .from('agenda_unificada')
        .select('*')
        .not('ambito', 'in', '("Oficial","Internacional","Nacional")')
        .order('fecha', { ascending: true });

      if (errorGestion) throw errorGestion;

      // Actualizamos el estado
      setDataMinisterio(oficialData || []);
      setDataCliente(gestionData || []);
      
      console.log(`✅ Datos cargados: ${oficialData?.length} Oficiales, ${gestionData?.length} Gestión.`);

    } catch (error) {
      console.error("❌ Error cargando agendas:", error);
    }
  };

  useEffect(() => { 
    if (session) cargarDatos(); 
  }, [session]); 

  const sincronizar = async () => {
    setSyncing(true);
    await cargarDatos();
    setRefreshTrigger(prev => prev + 1);
    setTimeout(() => setSyncing(false), 800); 
  };

  // --- PANTALLA DE CARGA ---
  if (loadingAuth) {
    return <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-400">Cargando sistema...</div>;
  }

  // --- PANTALLA DE LOGIN (Si no hay sesión) ---
  if (!session) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4">
        <div className="bg-slate-900/50 p-8 rounded-2xl border border-white/10 shadow-2xl max-w-md w-full text-center backdrop-blur-xl">
          <div className="mb-6 flex justify-center">
            <div className="p-4 bg-blue-500/20 rounded-full text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.5)]">
               <Lock size={40} />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-slate-100 mb-2">Acceso Restringido</h1>
          <p className="text-slate-400 mb-8">Sistema de Gestión SICyT. Por favor identifíquese.</p>
          
          <button 
            onClick={handleGoogleLogin}
            className="w-full py-3 px-4 bg-white hover:bg-slate-200 text-slate-900 font-bold rounded-xl transition-all flex items-center justify-center gap-3 shadow-lg"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
              <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
              <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
              <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
            </svg>
            Ingresar con Google
          </button>
        </div>
        <p className="mt-8 text-xs text-slate-600 font-mono">SICYT SECURE LOGIN v3.2</p>
      </div>
    );
  }

  // --- SI HAY SESIÓN, MOSTRAMOS EL DASHBOARD ORIGINAL ---
  const datosVisibles = vistaActual === 'cliente' ? dataCliente : dataMinisterio;

  const columnConfig: Record<string, string> = {
    fecha: "📅 Fecha",
    titulo: "📌 Evento / Motivo",
    lugar: "📍 Ubicación",
    funcionario: "👤 Funcionario",
    costo: "💰 Costo",
    ambito: "🌍 Ámbito",
    estado: "📊 Estado",
    num_expediente: "📂 Exp.",
    organizador: "🏢 Organiza"
  };

  const renderCell = (key: string, value: any, item: AgendaItem) => {
    if (!value && value !== 0) return <span className="text-slate-300">-</span>;
    if (key === 'costo' && typeof value === 'number') {
        const moneda = item.moneda || 'ARS';
        let colorClass = 'text-emerald-600'; 
        if (moneda === 'USD') colorClass = 'text-green-400';
        if (moneda === 'EUR') colorClass = 'text-blue-400';
        return (
            <div className="flex flex-col">
                <span className={`font-mono font-bold ${colorClass}`}>
                    {new Intl.NumberFormat('es-AR', { style: 'currency', currency: moneda }).format(value)}
                </span>
                {moneda !== 'ARS' && <span className="text-[10px] text-slate-500">{moneda}</span>}
            </div>
        );
    }
    if (key === 'fecha') {
        const safeDate = (dateStr: string) => new Date(dateStr + 'T12:00:00');
        const fInicio = safeDate(value);
        const txtInicio = fInicio.toLocaleDateString('es-AR', { day: '2-digit', month: 'short' });
        if (item.fecha_fin && item.fecha_fin !== value) {
            const fFin = safeDate(item.fecha_fin);
            const txtFin = fFin.toLocaleDateString('es-AR', { day: '2-digit', month: 'short' });
            return (
                <div className="flex flex-col text-xs leading-tight">
                    <span className="font-semibold text-slate-200">{txtInicio}</span>
                    <span className="text-slate-500">hasta {txtFin}</span>
                </div>
            );
        }
        return txtInicio;
    }
    if (key === 'ambito') {
        const color = value === 'Internacional' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700';
        return <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>{value}</span>;
    }
    return String(value).substring(0, 60);
  };

  const columnasMostrar = vistaActual === 'cliente' 
    ? ['fecha', 'titulo', 'funcionario', 'lugar', 'costo', 'estado']
    : ['fecha', 'titulo', 'organizador', 'lugar', 'ambito'];

  return (
    <div className="max-w-[1600px] mx-auto p-4 md:p-8 min-h-screen text-slate-300">
      
      {/* HEADER CON BOTÓN DE LOGOUT */}
      <header className="flex flex-col md:flex-row justify-between items-end mb-8 pb-6 border-b border-white/10 gap-4">
        <div className="w-full md:w-auto">
          <h1 className="text-3xl md:text-4xl font-bold bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 bg-clip-text text-transparent flex items-center gap-3">
            <LayoutDashboard className="text-blue-400" size={32} /> 
            SICYT Dashboard
          </h1>
          <p className="text-slate-400 text-sm mt-2 ml-1">
            Plataforma de Gestión Inteligente & IA • 
            <span className="text-blue-400 ml-2">Hola, {session?.user?.email}</span>
          </p>
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
            {syncing ? 'Sync' : 'Actualizar'}
          </button>
          
          <button 
            onClick={handleLogout} 
            title="Cerrar sesión"
            aria-label="Cerrar sesión"
            className="flex items-center gap-2 px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 rounded-lg transition-all text-sm font-medium"
          >
            <LogOut size={16} />
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
                    // --- 4. AQUI AGREGAMOS EL CLICK Y EL CURSOR POINTER ---
                    <tr 
                      key={i} 
                      onClick={() => handleRowClick(row)}
                      className="hover:bg-slate-50 transition-colors group cursor-pointer"
                    >
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
                        <h2 className="text-sm font-semibold text-slate-100">Asistente SICYT</h2>
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
      
      {/* --- 5. RENDERIZAR EL MODAL AL FINAL --- */}
      <EventModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        event={selectedEvent} 
      />

      <footer className="mt-12 mb-6 text-center">
        <p className="text-xs text-slate-600 font-mono">SICYT AI SYSTEM v3.2 • MULTIMONEDA ACTIVE</p>
      </footer>
    </div>
  );
}

export default App;