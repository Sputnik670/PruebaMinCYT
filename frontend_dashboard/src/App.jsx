import { useState, useEffect, useRef } from 'react';
import { 
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer 
} from 'recharts';
import './App.css';

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [syncing, setSyncing] = useState(false); // Estado para el botón de carga

  // Tu URL de Render
  const API_URL = "https://pruebamincyt.onrender.com";

  useEffect(() => {
    cargarDatos();
  }, []);

  const cargarDatos = () => {
    fetch(`${API_URL}/api/dashboard`)
      .then(res => {
        if (!res.ok) throw new Error(`Error HTTP: ${res.status}`);
        return res.json();
      })
      .then(resultado => {
        setData(resultado);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  };

  // --- FUNCIÓN PARA EL BOTÓN DE SINCRONIZACIÓN ---
  const sincronizarDatos = async () => {
    setSyncing(true);
    try {
      const res = await fetch(`${API_URL}/api/sync`, { method: 'POST' });
      const data = await res.json();
      if(data.status === 'error') throw new Error(data.msg);
      
      alert("¡Datos actualizados correctamente desde Google Sheets!");
      window.location.reload(); // Recargamos la página para ver los cambios
    } catch (e) {
      alert("Error al sincronizar: " + e.message);
    } finally {
      setSyncing(false);
    }
  };

  // Normalizador para que los gráficos entiendan mayúsculas/minúsculas
  const getVal = (row, keys) => {
    for (const k of keys) {
      if (row[k] !== undefined) return row[k];
      if (row[k.toLowerCase()] !== undefined) return row[k.toLowerCase()];
    }
    return 0;
  };

  const prepararBitacora = () => {
    if (!data?.bitacora) return [];
    const conteo = {};
    data.bitacora.forEach(row => {
      const tipo = getVal(row, ['Tipo', 'tipo']) || 'Otros';
      const horas = parseFloat(getVal(row, ['Duración (hs)', 'Duracion', 'duracion', 'horas']));
      conteo[tipo] = (conteo[tipo] || 0) + horas;
    });
    return Object.keys(conteo).map(k => ({ name: k, horas: conteo[k] }));
  };

  const prepararTendencia = () => {
    if (!data?.ventas_tabla) return [];
    return data.ventas_tabla.map((row, i) => ({
      fecha: getVal(row, ['Fecha', 'fecha']) || `Día ${i}`,
      monto: parseFloat(getVal(row, ['Monto', 'monto', 'inversion']))
    })).slice(-10);
  };

  if (loading) return <div style={{display:'flex', height:'100vh', alignItems:'center', justifyContent:'center'}}><h2>⏳ Conectando con Base de Datos...</h2></div>;
  if (error) return <div style={{color:'red', padding:50, textAlign:'center'}}><h1>⚠️ Error</h1><p>{error}</p></div>;

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '20px', fontFamily: 'Arial, sans-serif', minHeight: '100vh' }}>
      
      {/* HEADER CON EL BOTÓN NUEVO */}
      <header style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: '40px' }}>
        <div>
            <h1 style={{ fontSize: '2rem', margin:0 }}>🚀 Dashboard MinCYT</h1>
            <p style={{ color: '#888', margin:0 }}>Base de Datos en Vivo</p>
        </div>
        <button 
            onClick={sincronizarDatos} 
            disabled={syncing}
            style={{
                background: syncing ? '#555' : '#2ecc71',
                border: 'none', padding: '10px 20px', color: 'white', 
                borderRadius: '8px', cursor: syncing ? 'wait' : 'pointer',
                fontWeight: 'bold', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '10px'
            }}
        >
            {syncing ? '⏳ Sincronizando...' : '☁️ Actualizar Datos'}
        </button>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '30px', marginBottom: '40px' }}>
        <div style={{ background: '#1e1e1e', padding: '20px', borderRadius: '15px' }}>
          <h3 style={{ color: 'white' }}>⏱️ Horas por Tarea</h3>
          <div style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={prepararBitacora()}>
                <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                <XAxis dataKey="name" stroke="#ccc" />
                <YAxis stroke="#ccc" />
                <Tooltip contentStyle={{backgroundColor: '#333', border: 'none'}} />
                <Bar dataKey="horas" fill="#8884d8" name="Horas" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div style={{ background: '#1e1e1e', padding: '20px', borderRadius: '15px' }}>
          <h3 style={{ color: 'white' }}>💰 Tendencia de Inversión</h3>
          <div style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={prepararTendencia()}>
                <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                <XAxis dataKey="fecha" stroke="#ccc" />
                <YAxis stroke="#ccc" />
                <Tooltip contentStyle={{backgroundColor: '#333', border: 'none'}} formatter={(val) => `$ ${val.toLocaleString()}`}/>
                <Line type="monotone" dataKey="monto" stroke="#82ca9d" strokeWidth={3} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <SeccionAcordeon titulo="📋 Ventas (Base de Datos)" defaultAbierto={false}>
        <TablaGenerica datos={data.ventas_tabla} />
      </SeccionAcordeon>

      <SeccionAcordeon titulo="📅 Calendario (Base de Datos)" defaultAbierto={true}>
        <TablaGenerica datos={data.extra_tabla} />
      </SeccionAcordeon>

      <ChatBotWidget apiUrl={API_URL} />

    </div>
  );
}

// --- COMPONENTES UI ---
const ChatBotWidget = ({ apiUrl }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([{ sender: 'bot', text: '👋 Hola! Soy tu asistente IA con memoria. Pregúntame sobre los datos.' }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState(null);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  const handleSend = async () => {
    if (!input.trim() && !file) return;
    const userMsg = input;
    setMessages(prev => [...prev, { sender: 'user', text: userMsg, file: file?.name }]);
    setInput('');
    const fileToSend = file;
    setFile(null);
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append('pregunta', userMsg || "Analiza el archivo.");
      if (fileToSend) formData.append('file', fileToSend);

      const res = await fetch(`${apiUrl}/api/chat`, { method: 'POST', body: formData });
      const data = await res.json();
      setMessages(prev => [...prev, { sender: 'bot', text: data.respuesta }]);
    } catch (error) {
      setMessages(prev => [...prev, { sender: 'bot', text: 'Error al conectar.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ position: 'fixed', bottom: 20, right: 20, zIndex: 1000 }}>
      {!isOpen && <button onClick={() => setIsOpen(true)} style={{width:60, height:60, borderRadius:'50%', fontSize:30, cursor:'pointer'}}>🤖</button>}
      {isOpen && (
        <div style={{ width: 350, height: 500, background: '#1a1a1a', borderRadius: 12, display: 'flex', flexDirection: 'column', border:'1px solid #444', overflow:'hidden' }}>
          <div style={{ padding: 15, background: '#646cff', color: 'white', display:'flex', justifyContent:'space-between' }}>
            <strong>Asistente IA</strong>
            <button onClick={() => setIsOpen(false)} style={{background:'transparent', border:'none', color:'white', cursor:'pointer'}}>✕</button>
          </div>
          <div style={{ flex: 1, padding: 15, overflowY: 'auto', display:'flex', flexDirection:'column', gap:10 }}>
            {messages.map((msg, i) => (
              <div key={i} style={{ alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start', background: msg.sender === 'user' ? '#0051ff' : '#333', padding: 10, borderRadius: 8, maxWidth: '85%' }}>
                {msg.file && <div style={{fontSize:'0.8em', background:'#00000030', padding:2, borderRadius:4}}>📎 {msg.file}</div>}
                {msg.text}
              </div>
            ))}
            {loading && <div style={{color:'#888'}}>Escribiendo...</div>}
            <div ref={messagesEndRef} />
          </div>
          <div style={{ padding: 10, borderTop: '1px solid #333', display:'flex', gap:5, background:'#222' }}>
            <button onClick={() => fileInputRef.current.click()} style={{background:'#444'}}>+<input type="file" ref={fileInputRef} style={{display:'none'}} onChange={e => setFile(e.target.files[0])} /></button>
            <input value={input} onChange={e => setInput(e.target.value)} onKeyPress={e => e.key === 'Enter' && handleSend()} placeholder="Escribe..." style={{flex:1, padding:8, borderRadius:4, border:'none', background:'#333', color:'white'}} />
            <button onClick={handleSend} style={{background:'#646cff'}}>➤</button>
          </div>
        </div>
      )}
    </div>
  );
};

const SeccionAcordeon = ({ titulo, children, defaultAbierto }) => {
  const [abierto, setAbierto] = useState(defaultAbierto);
  return (
    <div style={{ marginBottom: 20, border: '1px solid #333', borderRadius: 8 }}>
      <button onClick={() => setAbierto(!abierto)} style={{ width: '100%', padding: 15, background: '#2c3e50', color: 'white', textAlign: 'left', border:'none', cursor:'pointer' }}>{titulo} {abierto ? '▼' : '▶'}</button>
      {abierto && <div style={{ padding: 15, background:'#1a1a1a' }}>{children}</div>}
    </div>
  );
};

const TablaGenerica = ({ datos }) => {
  if (!datos || datos.length === 0) return <p>Sin datos.</p>;
  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 600 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #555' }}>
            {Object.keys(datos[0]).map(k => <th key={k} style={{ padding: 10, textAlign:'left', textTransform:'capitalize' }}>{k}</th>)}
          </tr>
        </thead>
        <tbody>
          {datos.map((row, i) => (
            <tr key={i} style={{ borderBottom: '1px solid #444' }}>
              {Object.values(row).map((v, j) => <td key={j} style={{ padding: 10 }}>{v}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default App;