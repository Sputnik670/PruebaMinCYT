import { useState, useEffect, useRef } from 'react';
import { 
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer 
} from 'recharts';
import './App.css';

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // URL de tu Backend en Render
  const API_URL = "https://pruebamincyt.onrender.com";

  useEffect(() => {
    console.log("📡 Conectando...");
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
  }, []);

  const prepararBitacora = () => {
    if (!data?.bitacora) return [];
    const conteo = {};
    data.bitacora.forEach(row => {
      const tipo = row['Tipo'] || 'Otros';
      // Corrección de horas
      const horas = parseFloat(row['Duración (hs)'] || row['Duracion']) || 0;
      conteo[tipo] = (conteo[tipo] || 0) + horas;
    });
    return Object.keys(conteo).map(k => ({ name: k, horas: conteo[k] }));
  };

  if (loading) return <div style={{display:'flex', height:'100vh', alignItems:'center', justifyContent:'center'}}><h2>⏳ Cargando...</h2></div>;
  if (error) return <div style={{color:'red', padding:50, textAlign:'center'}}><h1>⚠️ Error</h1><p>{error}</p></div>;

  return (
    <div style={{ 
      maxWidth: '1200px', margin: '0 auto', padding: '20px', 
      fontFamily: 'Arial, sans-serif', minHeight: '100vh', overflowY: 'auto'
    }}>
      <header style={{ textAlign: 'center', marginBottom: '40px' }}>
        <h1 style={{ fontSize: '2.5rem' }}>🚀 Dashboard Maestro V2</h1>
        <p style={{ color: '#666' }}>Gestión Inteligente con IA</p>
      </header>

      {/* GRÁFICOS */}
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
              <LineChart data={data.tendencia_grafico}>
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

      {/* ACORDEONES */}
      <SeccionAcordeon titulo="📋 Registros de Ventas (Histórico)" defaultAbierto={false}>
        <TablaGenerica datos={data.ventas_tabla} filasPorPagina={5} />
      </SeccionAcordeon>

      <SeccionAcordeon titulo="📅 Calendario Internacionales" defaultAbierto={true}>
        {data.extra_tabla && data.extra_tabla.length > 0 ? (
          <TablaGenerica datos={data.extra_tabla} filasPorPagina={10} />
        ) : (
          <p style={{ color: '#666', fontStyle: 'italic' }}>Sin datos disponibles.</p>
        )}
      </SeccionAcordeon>

      {/* --- AQUÍ ESTÁ EL WIDGET DEL CHAT --- */}
      <ChatBotWidget apiUrl={API_URL} />

    </div>
  );
}

// --- COMPONENTE CHATBOT ---
const ChatBotWidget = ({ apiUrl }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { sender: 'bot', text: '👋 Hola! Soy tu asistente de IA. Pregúntame sobre los datos del dashboard.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;
    
    const userMsg = input;
    setMessages(prev => [...prev, { sender: 'user', text: userMsg }]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch(`${apiUrl}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pregunta: userMsg })
      });
      const data = await res.json();
      setMessages(prev => [...prev, { sender: 'bot', text: data.respuesta }]);
    } catch (error) {
      setMessages(prev => [...prev, { sender: 'bot', text: 'Error al conectar con el cerebro.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ position: 'fixed', bottom: '20px', right: '20px', zIndex: 1000 }}>
      {!isOpen && (
        <button 
          onClick={() => setIsOpen(true)}
          style={{
            width: '60px', height: '60px', borderRadius: '50%', background: '#646cff', 
            color: 'white', border: 'none', cursor: 'pointer', fontSize: '30px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}
        >
          🤖
        </button>
      )}

      {isOpen && (
        <div style={{
          width: '350px', height: '500px', background: '#1a1a1a', borderRadius: '12px',
          boxShadow: '0 8px 24px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column',
          overflow: 'hidden', border: '1px solid #333'
        }}>
          <div style={{ padding: '15px', background: '#646cff', color: 'white', display: 'flex', justifyContent: 'space-between' }}>
            <strong>Asistente IA</strong>
            <button onClick={() => setIsOpen(false)} style={{background:'transparent', border:'none', color:'white', cursor:'pointer'}}>✕</button>
          </div>
          <div style={{ flex: 1, padding: '15px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {messages.map((msg, i) => (
              <div key={i} style={{
                alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                background: msg.sender === 'user' ? '#646cff' : '#333',
                color: 'white', padding: '10px', borderRadius: '8px', maxWidth: '80%', fontSize: '0.9em'
              }}>
                {msg.text}
              </div>
            ))}
            {loading && <div style={{color:'#888', fontStyle:'italic', fontSize:'0.8em'}}>Escribiendo...</div>}
            <div ref={messagesEndRef} />
          </div>
          <div style={{ padding: '10px', borderTop: '1px solid #333', display: 'flex', gap: '5px' }}>
            <input 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Pregunta algo..."
              style={{ flex: 1, padding: '10px', borderRadius: '6px', border: '1px solid #444', background: '#222', color: 'white' }}
            />
            <button onClick={handleSend} style={{padding:'10px', borderRadius:'6px', background:'#646cff', color:'white', border:'none', cursor:'pointer'}}>➤</button>
          </div>
        </div>
      )}
    </div>
  );
};

// --- COMPONENTES UI (Acordeón y Tabla) ---
const SeccionAcordeon = ({ titulo, children, defaultAbierto = false }) => {
  const [abierto, setAbierto] = useState(defaultAbierto);
  return (
    <div style={{ marginBottom: '20px', borderRadius: '10px', overflow: 'hidden', border: '1px solid #333' }}>
      <button onClick={() => setAbierto(!abierto)} style={{ width: '100%', background: '#2c3e50', color: 'white', padding: '15px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', border: 'none', cursor: 'pointer', fontSize: '1.1rem', fontWeight: 'bold', textAlign: 'left' }}>
        <span>{titulo}</span>
        <span style={{ transform: abierto ? 'rotate(180deg)' : 'rotate(0deg)', transition: '0.3s' }}>▼</span>
      </button>
      {abierto && <div style={{ padding: '20px', background: '#1a1a1a' }}>{children}</div>}
    </div>
  );
};

const TablaGenerica = ({ datos, filasPorPagina = 10 }) => {
  const [paginaActual, setPaginaActual] = useState(1);
  if (!datos || datos.length === 0) return <p>Sin datos.</p>;
  const totalPaginas = Math.ceil(datos.length / filasPorPagina);
  const indiceUltimo = paginaActual * filasPorPagina;
  const indicePrimero = indiceUltimo - filasPorPagina;
  const datosVisibles = datos.slice(indicePrimero, indiceUltimo);
  const columnas = Object.keys(datos[0]);
  const cambiarPagina = (nuevaPagina) => { if (nuevaPagina >= 1 && nuevaPagina <= totalPaginas) setPaginaActual(nuevaPagina); };

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', color: '#ccc', minWidth: '600px' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #555', textAlign:'left' }}>
            {columnas.map(k => <th key={k} style={{ padding: 10, color: '#fff' }}>{k}</th>)}
          </tr>
        </thead>
        <tbody>
          {datosVisibles.map((row, i) => (
            <tr key={i} style={{ borderBottom: '1px solid #444' }}>
              {columnas.map((col, j) => <td key={j} style={{ padding: 10 }}>{row[col]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
      {totalPaginas > 1 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: '20px', marginTop: '20px', color: '#ccc' }}>
          <button onClick={() => cambiarPagina(paginaActual - 1)} disabled={paginaActual === 1} style={{padding:'5px 10px', cursor:'pointer', background:'#444', color:'white', border:'none', borderRadius:'4px'}}>⬅</button>
          <span>Pág {paginaActual} de {totalPaginas}</span>
          <button onClick={() => cambiarPagina(paginaActual + 1)} disabled={paginaActual === totalPaginas} style={{padding:'5px 10px', cursor:'pointer', background:'#444', color:'white', border:'none', borderRadius:'4px'}}>➡</button>
        </div>
      )}
    </div>
  );
};

export default App;