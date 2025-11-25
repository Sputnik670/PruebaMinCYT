import { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [data, setData] = useState([]);
  const [syncing, setSyncing] = useState(false);
  
  // Tu URL de Render
  const API_URL = "https://pruebamincyt.onrender.com";

  // Cargar datos
  const cargarDatos = () => {
    fetch(`${API_URL}/api/data`)
      .then(res => res.json())
      .then(datos => {
        // Validación simple para asegurar que sea una lista
        if (Array.isArray(datos)) {
          setData(datos);
        }
      })
      .catch(console.error);
  };

  useEffect(() => { cargarDatos(); }, []);

  // Sincronizar
  const sincronizar = async () => {
    setSyncing(true);
    try {
      await fetch(`${API_URL}/api/sync`, { method: 'POST' });
      alert("Actualizado");
      cargarDatos(); 
    } catch (e) { alert("Error: " + e.message); }
    setSyncing(false);
  };

  // --- LÓGICA DINÁMICA ---
  // Obtenemos los nombres de las columnas automáticamente del primer elemento
  const columnas = data.length > 0 ? Object.keys(data[0]) : [];

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '20px', fontFamily: 'sans-serif', background: '#121212', minHeight: '100vh', color: 'white' }}>
      
      <header style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 40, paddingBottom: 20, borderBottom: '1px solid #333' }}>
        <div>
          <h1 style={{margin:0}}>🌍 Calendario MinCYT</h1>
          <p style={{color:'#888', margin:0}}>Gestión Inteligente</p>
        </div>
        <button onClick={sincronizar} disabled={syncing} style={{padding:'12px 24px', background: '#2ecc71', border:'none', borderRadius:8, cursor:'pointer', fontWeight:'bold'}}>
          {syncing ? '⏳' : '↻ Actualizar'}
        </button>
      </header>

      {/* TABLA AUTOMÁTICA (Todoterreno) */}
      <div style={{ background: '#1e1e1e', padding: 20, borderRadius: 12, overflowX: 'auto' }}>
        
        {data.length === 0 ? (
          <div style={{padding:40, textAlign:'center', color:'#666'}}>
            <p>Cargando datos o tabla vacía...</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 900 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #444', textAlign:'left', color: '#aaa' }}>
                {/* Dibuja los títulos automáticamente */}
                {columnas.map((col) => (
                  <th key={col} style={{padding:15, textTransform:'capitalize'}}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* Dibuja las filas automáticamente */}
              {data.map((row, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #333' }}>
                  {columnas.map((col) => (
                    <td key={col} style={{padding:15}}>
                      {/* Si es texto largo lo corta, si es null pone guion */}
                      {row[col] ? row[col].toString() : '-'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <ChatBotWidget apiUrl={API_URL} />
    </div>
  );
}

const ChatBotWidget = ({ apiUrl }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([{ sender: 'bot', text: 'Hola. ¿Qué necesitas saber?' }]);
  const [input, setInput] = useState('');
  const msgsRef = useRef(null);

  useEffect(() => msgsRef.current?.scrollIntoView({ behavior: "smooth" }), [messages, isOpen]);

  const send = async () => {
    if (!input) return;
    const txt = input; setInput('');
    setMessages(p => [...p, { sender: 'user', text: txt }]);
    try {
      const res = await fetch(`${apiUrl}/api/chat`, { 
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: txt }) 
      });
      const dat = await res.json();
      setMessages(p => [...p, { sender: 'bot', text: dat.response }]);
    } catch (e) { setMessages(p => [...p, { sender: 'bot', text: "Error de conexión." }]); }
  };

  return (
    <div style={{ position: 'fixed', bottom: 20, right: 20, zIndex: 9999 }}>
      {!isOpen && <button onClick={()=>setIsOpen(true)} style={{width:60, height:60, borderRadius:'50%', fontSize:30, cursor:'pointer', background:'#646cff', border:'none'}}>💬</button>}
      {isOpen && (
        <div style={{ width: 350, height: 500, background: '#222', borderRadius: 12, display:'flex', flexDirection:'column', border:'1px solid #444' }}>
            <div style={{padding:15, background:'#646cff', display:'flex', justifyContent:'space-between'}}>
                <strong>Asistente IA</strong>
                <button onClick={()=>setIsOpen(false)} style={{background:'none', border:'none', color:'white', cursor:'pointer'}}>✕</button>
            </div>
            <div style={{flex:1, overflowY:'auto', padding:10, display:'flex', flexDirection:'column', gap:10}}>
                {messages.map((m,i) => <div key={i} style={{alignSelf: m.sender==='user'?'flex-end':'flex-start', background: m.sender==='user'?'#4f46e5':'#333', padding:10, borderRadius:8}}>{m.text}</div>)}
                <div ref={msgsRef}></div>
            </div>
            <div style={{padding:10, display:'flex'}}>
                <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==='Enter'&&send()} style={{flex:1, padding:10, borderRadius:4, border:'none'}} placeholder="Escribe..." />
                <button onClick={send} style={{marginLeft:5, padding:'0 15px'}}>➤</button>
            </div>
        </div>
      )}
    </div>
  );
}

export default App;