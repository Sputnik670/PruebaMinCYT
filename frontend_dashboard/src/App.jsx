import { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [data, setData] = useState([]);
  const [rawDebug, setRawDebug] = useState(null); // Variable para ver los datos crudos
  const [syncing, setSyncing] = useState(false);
  const [verTodos, setVerTodos] = useState(false);
  
  const API_URL = "https://pruebamincyt.onrender.com";

  const cargarDatos = () => {
    fetch(`${API_URL}/api/data`)
      .then(res => res.json())
      .then(datos => {
        console.log("Datos:", datos);
        setData(datos);
        // Guardamos el primer dato para verlo en pantalla
        if (datos && datos.length > 0) {
            setRawDebug(datos[0]); 
        }
      })
      .catch(err => alert("Error cargando: " + err));
  };

  useEffect(() => { cargarDatos(); }, []);

  const sincronizar = async () => {
    setSyncing(true);
    try {
      await fetch(`${API_URL}/api/sync`, { method: 'POST' });
      alert("Sincronizado.");
      cargarDatos(); 
    } catch (e) { alert(e.message); }
    setSyncing(false);
  };

  const datosVisibles = verTodos ? data : data.slice(0, 5);

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '20px', fontFamily: 'sans-serif', background: '#121212', minHeight: '100vh', color: 'white' }}>
      
      <header style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 40, paddingBottom: 20, borderBottom: '1px solid #333' }}>
        <h1>🌍 Calendario MinCYT</h1>
        <button onClick={sincronizar} disabled={syncing} style={{padding:'12px 24px', background: '#2ecc71', border:'none', borderRadius:8, cursor:'pointer', fontWeight:'bold'}}>
          {syncing ? '⏳' : 'Actualizar'}
        </button>
      </header>

      {/* --- ZONA DE DIAGNÓSTICO (Esto nos dirá la verdad) --- */}
      <div style={{background: '#333', padding: 20, borderRadius: 8, marginBottom: 20, border: '2px solid yellow'}}>
        <h3>🕵️‍♂️ ZONA DE DIAGNÓSTICO</h3>
        <p>Esto es lo que el Excel está enviando realmente:</p>
        <pre style={{textAlign: 'left', overflow: 'auto', color: '#0f0'}}>
            {rawDebug ? JSON.stringify(rawDebug, null, 2) : "No han llegado datos aún..."}
        </pre>
      </div>
      {/* ----------------------------------------------------- */}

      <div style={{ background: '#1e1e1e', padding: 20, borderRadius: 12, overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 900 }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #444', textAlign:'left', color: '#aaa' }}>
              <th style={{padding:15}}>Fecha</th>
              <th style={{padding:15}}>Evento</th>
              <th style={{padding:15}}>Lugar</th>
            </tr>
          </thead>
          <tbody>
            {datosVisibles.map((row, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #333' }}>
                {/* Intento genérico de mostrar algo */}
                <td style={{padding:15}}>{Object.values(row)[0]}</td> 
                <td style={{padding:15}}>{Object.values(row)[1]}</td>
                <td style={{padding:15}}>{Object.values(row)[2]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ChatBotWidget apiUrl={API_URL} />
    </div>
  );
}

const ChatBotWidget = ({ apiUrl }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([{ sender: 'bot', text: 'Hola.' }]);
  const [input, setInput] = useState('');
  
  const send = async () => {
    if (!input) return;
    const txt = input; setInput('');
    setMessages(p => [...p, { sender: 'user', text: txt }]);
    try {
      const res = await fetch(`${apiUrl}/api/chat`, { 
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: txt }) 
      });
      const dat = await res.json();
      setMessages(p => [...p, { sender: 'bot', text: dat.response }]);
    } catch (e) { setMessages(p => [...p, { sender: 'bot', text: "Error" }]); }
  };

  return (
    <div style={{ position: 'fixed', bottom: 20, right: 20, zIndex: 9999 }}>
      {!isOpen && <button onClick={()=>setIsOpen(true)} style={{width:60, height:60, borderRadius:'50%', fontSize:30, cursor:'pointer'}}>💬</button>}
      {isOpen && (
        <div style={{ width: 300, height: 400, background: '#222', borderRadius: 12, display:'flex', flexDirection:'column', padding:10, border:'1px solid #444' }}>
            <button onClick={()=>setIsOpen(false)} style={{alignSelf:'flex-end'}}>✕</button>
            <div style={{flex:1, overflowY:'auto'}}>
                {messages.map((m,i) => <div key={i} style={{color: m.sender==='user'?'#aaf':'#fff'}}>{m.text}</div>)}
            </div>
            <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==='Enter'&&send()} placeholder="Escribe..." />
        </div>
      )}
    </div>
  );
}

export default App;