import { useState, useEffect, useRef } from 'react';
import './App.css';

// --- URL DEL BACKEND (Asegúrate que coincida con tu deploy de Render) ---
// Si estás en local, usa http://localhost:10000 o el puerto que use tu backend
const API_URL = "https://pruebamincyt.onrender.com";

function App() {
  const [data, setData] = useState([]);
  const [syncing, setSyncing] = useState(false);
  const [mostrarTabla, setMostrarTabla] = useState(true); // Estado para contraer tabla

  // Cargar datos
  const cargarDatos = () => {
    fetch(`${API_URL}/api/data`)
      .then(res => res.json())
      .then(datos => {
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
      alert("Datos actualizados correctamente.");
      cargarDatos(); 
    } catch (e) { alert("Error al sincronizar: " + e.message); }
    setSyncing(false);
  };

  const columnas = data.length > 0 ? Object.keys(data[0]) : [];

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '20px', fontFamily: 'sans-serif', background: '#121212', minHeight: '100vh', color: 'white' }}>
      
      <header style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: 20, paddingBottom: 20, borderBottom: '1px solid #333' }}>
        <div>
          <h1 style={{margin:0, fontSize: '1.8rem'}}>🌍 Calendario MinCYT</h1>
          <p style={{color:'#888', margin:0}}>Gestión Inteligente</p>
        </div>
        <div style={{display:'flex', gap:'10px'}}>
            <button onClick={() => setMostrarTabla(!mostrarTabla)} style={{padding:'10px 20px', background: '#444', border:'none', borderRadius:8, cursor:'pointer', color:'white'}}>
                {mostrarTabla ? '🙈 Ocultar Tabla' : '👁️ Ver Tabla'}
            </button>
            <button onClick={sincronizar} disabled={syncing} style={{padding:'10px 20px', background: '#2ecc71', border:'none', borderRadius:8, cursor:'pointer', fontWeight:'bold', color:'#fff'}}>
            {syncing ? '⏳...' : '↻ Actualizar'}
            </button>
        </div>
      </header>

      {/* TABLA CONTRAÍBLE */}
      {mostrarTabla && (
        <div style={{ background: '#1e1e1e', padding: 20, borderRadius: 12, overflowX: 'auto', marginBottom: 40, boxShadow: '0 4px 6px rgba(0,0,0,0.3)' }}>
            {data.length === 0 ? (
            <div style={{padding:40, textAlign:'center', color:'#666'}}>
                <p>Cargando datos o tabla vacía...</p>
            </div>
            ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 900, fontSize: '0.9rem' }}>
                <thead>
                <tr style={{ borderBottom: '2px solid #444', textAlign:'left', color: '#aaa' }}>
                    {columnas.map((col) => (
                    <th key={col} style={{padding:12, textTransform:'capitalize'}}>{col}</th>
                    ))}
                </tr>
                </thead>
                <tbody>
                {data.slice(0, 20).map((row, i) => ( // Limitamos a 20 filas visuales por rendimiento
                    <tr key={i} style={{ borderBottom: '1px solid #333' }}>
                    {columnas.map((col) => (
                        <td key={col} style={{padding:12, color: '#ddd'}}>
                        {row[col] ? row[col].toString().substring(0, 50) + (row[col].toString().length > 50 ? '...' : '') : '-'}
                        </td>
                    ))}
                    </tr>
                ))}
                </tbody>
            </table>
            )}
            {data.length > 20 && <p style={{textAlign:'center', color:'#666', fontSize:'0.8rem', marginTop:10}}>Mostrando primeras 20 filas de {data.length}</p>}
        </div>
      )}

      <ChatBotWidget apiUrl={API_URL} />
    </div>
  );
}

const ChatBotWidget = ({ apiUrl }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([{ sender: 'bot', text: 'Hola. Soy tu asistente del MinCYT. ¿Qué necesitas saber?' }]);
  const [input, setInput] = useState('');
  const [isListening, setIsListening] = useState(false);
  const msgsRef = useRef(null);

  useEffect(() => msgsRef.current?.scrollIntoView({ behavior: "smooth" }), [messages, isOpen]);

  const send = async (textOverride) => {
    const textToSend = textOverride || input;
    if (!textToSend) return;
    
    setInput('');
    setMessages(p => [...p, { sender: 'user', text: textToSend }]);
    
    // Mensaje de carga
    setMessages(p => [...p, { sender: 'bot', text: 'Thinking...', isLoading: true }]);

    try {
      const res = await fetch(`${apiUrl}/api/chat`, { 
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: textToSend }) 
      });
      const dat = await res.json();
      
      // Reemplazar mensaje de carga con respuesta real
      setMessages(p => {
        const filtered = p.filter(m => !m.isLoading);
        return [...filtered, { sender: 'bot', text: dat.response }];
      });

    } catch (e) { 
      setMessages(p => {
        const filtered = p.filter(m => !m.isLoading);
        return [...filtered, { sender: 'bot', text: "Error de conexión con el servidor." }];
      });
    }
  };

  // --- RECONOCIMIENTO DE VOZ ---
  const startListening = () => {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert("Tu navegador no soporta reconocimiento de voz (Prueba Chrome).");
      return;
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = 'es-ES';
    
    recognition.onstart = () => setIsListening(true);
    recognition.onend = () => setIsListening(false);
    
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setInput(transcript);
      setTimeout(() => send(transcript), 500); // Auto-enviar después de hablar
    };
    
    recognition.start();
  };

  return (
    <div style={{ position: 'fixed', bottom: 20, right: 20, zIndex: 9999 }}>
      {!isOpen && <button onClick={()=>setIsOpen(true)} style={{width:60, height:60, borderRadius:'50%', fontSize:30, cursor:'pointer', background:'#646cff', border:'none', boxShadow:'0 4px 10px rgba(0,0,0,0.5)'}}>💬</button>}
      {isOpen && (
        <div style={{ width: 350, height: 500, background: '#222', borderRadius: 12, display:'flex', flexDirection:'column', border:'1px solid #444', boxShadow:'0 10px 25px rgba(0,0,0,0.5)' }}>
            <div style={{padding:15, background:'#646cff', borderRadius: '12px 12px 0 0', display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                <strong style={{color:'white'}}>Asistente IA</strong>
                <button onClick={()=>setIsOpen(false)} style={{background:'none', border:'none', color:'white', cursor:'pointer', fontSize:'1.2rem'}}>✕</button>
            </div>
            <div style={{flex:1, overflowY:'auto', padding:15, display:'flex', flexDirection:'column', gap:10}}>
                {messages.map((m,i) => (
                    <div key={i} style={{
                        alignSelf: m.sender==='user'?'flex-end':'flex-start', 
                        background: m.sender==='user'?'#4f46e5':'#333', 
                        padding:'10px 14px', 
                        borderRadius:8, 
                        maxWidth:'80%',
                        lineHeight: '1.4',
                        fontSize: '0.95rem',
                        color: m.isLoading ? '#aaa' : 'white',
                        fontStyle: m.isLoading ? 'italic' : 'normal'
                    }}>
                        {m.text}
                    </div>
                ))}
                <div ref={msgsRef}></div>
            </div>
            <div style={{padding:10, display:'flex', gap:5, borderTop:'1px solid #333'}}>
                <button 
                    onClick={startListening} 
                    style={{padding:'10px', borderRadius:'50%', border:'none', background: isListening ? '#ef4444' : '#333', cursor:'pointer', transition:'all 0.2s'}}
                    title="Hablar"
                >
                    {isListening ? '🛑' : '🎙️'}
                </button>
                <input 
                    value={input} 
                    onChange={e=>setInput(e.target.value)} 
                    onKeyDown={e=>e.key==='Enter'&&send()} 
                    style={{flex:1, padding:10, borderRadius:20, border:'1px solid #444', background:'#1a1a1a', color:'white', outline:'none'}} 
                    placeholder="Escribe aquí..." 
                />
                <button onClick={() => send()} style={{padding:'0 15px', background:'none', border:'none', cursor:'pointer', fontSize:'1.2rem'}}>➤</button>
            </div>
        </div>
      )}
    </div>
  );
}

export default App;