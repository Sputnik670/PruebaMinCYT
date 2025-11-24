import { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [data, setData] = useState([]);
  const [syncing, setSyncing] = useState(false);
  // Tu URL de Render
  const API_URL = "https://pruebamincyt.onrender.com";

  // Función para cargar datos (Usa el endpoint NUEVO /api/data)
  const cargarDatos = () => {
    fetch(`${API_URL}/api/data`)
      .then(res => {
        if (!res.ok) throw new Error(`Error servidor: ${res.status}`);
        return res.json();
      })
      .then(setData)
      .catch(console.error);
  };

  // Cargar al inicio
  useEffect(() => { cargarDatos(); }, []);

  // Función de Sincronización
  const sincronizar = async () => {
    setSyncing(true);
    try {
      const res = await fetch(`${API_URL}/api/sync`, { method: 'POST' });
      const json = await res.json();
      if(json.status === 'error') throw new Error(json.msg);
      
      alert(json.msg || "¡Sincronización exitosa!");
      cargarDatos(); 
    } catch (e) { 
      alert("Error al sincronizar: " + e.message); 
    }
    setSyncing(false);
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '20px', fontFamily: 'sans-serif', background: '#121212', minHeight: '100vh', color: 'white' }}>
      
      {/* HEADER */}
      <header style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 40, paddingBottom: 20, borderBottom: '1px solid #333' }}>
        <div>
          <h1 style={{margin:0}}>🌍 Calendario Internacional</h1>
          <p style={{color:'#888', margin:0}}>MinCYT Gestión Inteligente</p>
        </div>
        <button onClick={sincronizar} disabled={syncing} style={{padding:'12px 24px', background: syncing ? '#555':'#2ecc71', color:'white', border:'none', borderRadius:8, cursor:'pointer', fontWeight:'bold', fontSize:'1rem'}}>
          {syncing ? '⏳ ...' : '☁️ Actualizar Excel'}
        </button>
      </header>

      {/* TABLA DE DATOS */}
      <div style={{ background: '#1e1e1e', padding: 20, borderRadius: 12, overflowX: 'auto', boxShadow: '0 4px 10px rgba(0,0,0,0.3)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 900 }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #444', textAlign:'left', color: '#aaa' }}>
              <th style={{padding:15}}>Fecha</th>
              <th style={{padding:15}}>Evento</th>
              <th style={{padding:15}}>Lugar</th>
              <th style={{padding:15}}>Ámbito</th>
              <th style={{padding:15}}>Participante</th>
              <th style={{padding:15}}>¿Pagan?</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #333' }}>
                <td style={{padding:15, whiteSpace:'nowrap'}}>{row.fecha_inicio}</td>
                <td style={{padding:15, fontWeight:'bold', color:'#fff'}}>{row.titulo}</td>
                <td style={{padding:15}}>{row.lugar}</td>
                <td style={{padding:15}}><span style={{background: row.nac_intl?.toLowerCase().includes('intl') ?'#4f46e5':'#059669', padding:'4px 8px', borderRadius:4, fontSize:'0.8em', fontWeight:'bold'}}>{row.nac_intl}</span></td>
                <td style={{padding:15}}>{row.participante}</td>
                <td style={{padding:15}}>{row.pagan}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data.length === 0 && <div style={{padding:40, textAlign:'center', color:'#666'}}>
          <h3>No hay datos cargados</h3>
          <p>Presiona el botón verde para traer la información del Excel.</p>
        </div>}
      </div>

      {/* CHATBOT */}
      <ChatBotWidget apiUrl={API_URL} />
    </div>
  );
}

const ChatBotWidget = ({ apiUrl }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([{ sender: 'bot', text: 'Hola. Tengo acceso al Calendario. ¿Qué necesitas saber?' }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState(null);
  const msgsRef = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => msgsRef.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  const send = async () => {
    if (!input && !file) return;
    const txt = input; setInput('');
    const f = file; setFile(null);
    
    setMessages(p => [...p, { sender: 'user', text: txt, file: f?.name }]);
    setLoading(true);
    
    const fd = new FormData(); 
    fd.append('pregunta', txt || "Analiza este archivo");
    if(f) fd.append('file', f);

    try {
      const res = await fetch(`${apiUrl}/api/chat`, { method:'POST', body:fd });
      const dat = await res.json();
      setMessages(p => [...p, { sender: 'bot', text: dat.respuesta }]);
    } catch {
      setMessages(p => [...p, { sender: 'bot', text: "Error de conexión." }]);
    }
    setLoading(false);
  };

  return (
    <div style={{ position: 'fixed', bottom: 20, right: 20 }}>
      {!isOpen && <button onClick={()=>setIsOpen(true)} style={{width:60, height:60, borderRadius:'50%', fontSize:30, cursor:'pointer', background:'#646cff', border:'none', boxShadow:'0 4px 12px rgba(0,0,0,0.3)'}}>💬</button>}
      {isOpen && (
        <div style={{ width: 350, height: 500, background: '#222', borderRadius: 12, display:'flex', flexDirection:'column', border:'1px solid #444', overflow:'hidden', boxShadow:'0 10px 30px rgba(0,0,0,0.5)' }}>
          <div style={{padding:15, background:'#646cff', color:'white', display:'flex', justifyContent:'space-between', alignItems:'center'}}>
            <strong>Asistente IA</strong> <button onClick={()=>setIsOpen(false)} style={{background:'none', border:'none', color:'white', cursor:'pointer'}}>✕</button>
          </div>
          <div style={{flex:1, padding:15, overflowY:'auto', display:'flex', flexDirection:'column', gap:10}}>
            {messages.map((m,i) => (
              <div key={i} style={{alignSelf: m.sender==='user'?'flex-end':'flex-start', background: m.sender==='user'?'#4f46e5':'#333', padding:'10px 15px', borderRadius:10, color:'white', maxWidth:'85%', lineHeight:'1.4'}}>
                {m.file && <div style={{fontSize:'0.8em', background:'rgba(0,0,0,0.2)', padding:'2px 6px', borderRadius:4, marginBottom:5}}>📎 {m.file}</div>}
                {m.text}
              </div>
            ))}
            {loading && <div style={{color:'#888', fontStyle:'italic'}}>Analizando...</div>}
            <div ref={msgsRef}></div>
          </div>
          <div style={{padding:10, borderTop:'1px solid #333', display:'flex', gap:5, background:'#1a1a1a'}}>
            <button onClick={()=>fileRef.current.click()} style={{background:'#333', color:'white', border:'1px solid #444', borderRadius:4, width:40}}>📎<input type="file" ref={fileRef} hidden onChange={e=>setFile(e.target.files[0])}/></button>
            {file && <span style={{fontSize:10, color:'#aaa', alignSelf:'center'}}>📄</span>}
            <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==='Enter'&&send()} style={{flex:1, padding:10, borderRadius:4, border:'none', background:'#333', color:'white'}} placeholder="Escribe..." />
            <button onClick={send} style={{background:'#646cff', border:'none', borderRadius:4, color:'white', padding:'0 15px'}}>➤</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;