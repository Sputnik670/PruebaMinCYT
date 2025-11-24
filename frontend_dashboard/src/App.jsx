import { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [data, setData] = useState([]);
  const [syncing, setSyncing] = useState(false);
  const [verTodos, setVerTodos] = useState(false); // Estado para desplegar tabla
  
  // Tu URL de Render
  const API_URL = "https://pruebamincyt.onrender.com";

  // Cargar datos
  const cargarDatos = () => {
    fetch(`${API_URL}/api/data`)
      .then(res => {
        if (!res.ok) throw new Error(`Error servidor: ${res.status}`);
        return res.json();
      })
      .then(setData)
      .catch(console.error);
  };

  useEffect(() => { cargarDatos(); }, []);

  // Sincronizar
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

  // Lógica de filtrado visual (5 filas o todas)
  const datosVisibles = verTodos ? data : data.slice(0, 5);

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

      {/* TABLA DE DATOS (Ahora con botón "Ver Más") */}
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
            {datosVisibles.map((row, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #333' }}>
                <td style={{padding:15, whiteSpace:'nowrap'}}>{row.fecha_inicio}</td>
                <td style={{padding:15, fontWeight:'bold', color:'#fff'}}>{row.titulo}</td>
                <td style={{padding:15}}>{row.lugar}</td>
                <td style={{padding:15}}>
                  <span style={{background: row.nac_intl?.toLowerCase().includes('intl') ?'#4f46e5':'#059669', padding:'4px 8px', borderRadius:4, fontSize:'0.8em', fontWeight:'bold'}}>
                    {row.nac_intl}
                  </span>
                </td>
                <td style={{padding:15}}>{row.participante}</td>
                <td style={{padding:15}}>{row.pagan}</td>
              </tr>
            ))}
          </tbody>
        </table>
        
        {/* Estado vacío */}
        {data.length === 0 && <div style={{padding:40, textAlign:'center', color:'#666'}}>
          <h3>No hay datos cargados</h3>
          <p>Presiona el botón verde para traer la información del Excel.</p>
        </div>}

        {/* Botón Desplegar/Contraer */}
        {data.length > 5 && (
          <div style={{textAlign:'center', marginTop:20, borderTop:'1px solid #333', paddingTop:10}}>
            <button 
              onClick={() => setVerTodos(!verTodos)}
              style={{background:'transparent', border:'1px solid #666', color:'#ccc', padding:'8px 16px', borderRadius:20, cursor:'pointer', transition:'0.3s'}}
            >
              {verTodos ? '⬆️ Ver menos' : `⬇️ Ver todos (${data.length} eventos)`}
            </button>
          </div>
        )}
      </div>

      {/* CHATBOT */}
      <ChatBotWidget apiUrl={API_URL} />
    </div>
  );
}

const ChatBotWidget = ({ apiUrl }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false); // Estado para tamaño gigante
  const [messages, setMessages] = useState([{ sender: 'bot', text: 'Hola. Tengo acceso al Calendario. ¿Qué necesitas saber?' }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState(null);
  const msgsRef = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => msgsRef.current?.scrollIntoView({ behavior: "smooth" }), [messages, isExpanded, isOpen]);

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

  // Estilos dinámicos
  const containerStyle = isExpanded ? 
    { width: '600px', height: '80vh', right: '20px', bottom: '20px' } : 
    { width: '350px', height: '500px', right: '20px', bottom: '20px' };

  return (
    <div style={{ position: 'fixed', zIndex: 9999, ...containerStyle, pointerEvents: 'none', display: 'flex', justifyContent: 'flex-end', alignItems: 'flex-end' }}>
      
      {/* Botón Flotante (Solo si está cerrado) */}
      {!isOpen && (
        <button onClick={()=>setIsOpen(true)} style={{pointerEvents: 'auto', width:60, height:60, borderRadius:'50%', fontSize:30, cursor:'pointer', background:'#646cff', border:'none', boxShadow:'0 4px 12px rgba(0,0,0,0.3)', display:'flex', justifyContent:'center', alignItems:'center'}}>
          💬
        </button>
      )}

      {/* Ventana de Chat */}
      {isOpen && (
        <div style={{ 
          width: '100%', 
          height: '100%', 
          background: '#222', 
          borderRadius: 12, 
          display:'flex', 
          flexDirection:'column', 
          border:'1px solid #444', 
          overflow:'hidden', 
          boxShadow:'0 10px 30px rgba(0,0,0,0.5)',
          pointerEvents: 'auto',
          transition: 'all 0.3s ease' // Animación suave al cambiar tamaño
        }}>
          <div style={{padding:15, background:'#646cff', color:'white', display:'flex', justifyContent:'space-between', alignItems:'center'}}>
            <strong style={{fontSize: isExpanded ? '1.2rem' : '1rem'}}>Asistente IA</strong>
            <div style={{display:'flex', gap:10}}>
              {/* Botón de ESTIRAR / CONTRAER */}
              <button 
                onClick={() => setIsExpanded(!isExpanded)} 
                title={isExpanded ? "Achicar" : "Agrandar"}
                style={{background:'rgba(0,0,0,0.2)', border:'none', color:'white', cursor:'pointer', borderRadius:4, padding:'2px 6px'}}
              >
                {isExpanded ? '📉' : 'square'}
              </button>
              {/* Botón de CERRAR */}
              <button onClick={()=>setIsOpen(false)} style={{background:'none', border:'none', color:'white', cursor:'pointer', fontSize:'1.2rem'}}>✕</button>
            </div>
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
            <button onClick={()=>fileRef.current.click()} style={{background:'#333', color:'white', border:'1px solid #444', borderRadius:4, width:40, cursor:'pointer'}} title="Adjuntar PDF">📎<input type="file" ref={fileRef} hidden onChange={e=>setFile(e.target.files[0])}/></button>
            {file && <span style={{fontSize:10, color:'#aaa', alignSelf:'center'}}>📄</span>}
            <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==='Enter'&&send()} style={{flex:1, padding:10, borderRadius:4, border:'none', background:'#333', color:'white'}} placeholder="Escribe..." />
            <button onClick={send} style={{background:'#646cff', border:'none', borderRadius:4, color:'white', padding:'0 15px', cursor:'pointer'}}>➤</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;