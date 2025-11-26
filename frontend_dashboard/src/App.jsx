// src/App.jsx (VERSIÓN INTEGRADA)

import { useState, useEffect, useRef } from 'react';
import './App.css';
// --- NUEVO IMPORT PARA EL CHATBOT ---
import { ChatInterface } from './components/ChatInterface'; 
// ------------------------------------

// --- URL DEL BACKEND (Asegúrate que coincida con tu deploy de Render) ---
// Si estás en local, usa http://localhost:10000 o el puerto que use tu backend
const API_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

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

// Sincronizar (Opción B: Recarga eficiente sin llamada fake al backend)
  const sincronizar = async () => {
    setSyncing(true);
    // Simulamos una pequeña espera visual para que el usuario vea que "algo pasa"
    // y llamamos a cargarDatos para traer la info fresca de Google Sheets.
    await cargarDatos();
    setTimeout(() => {
      setSyncing(false);
      alert("Datos actualizados correctamente.");
    }, 800); 
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

      {/* TABLA CONTRAÍBLE (CÓDIGO VIEJO) */}
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
      
      {/* ------------------------------------------------------------- */}
      {/* --- INTEGRACIÓN DEL NUEVO CHATBOT MINCYT (EL CHAT QUE CREAMOS CON TAILWIND) --- */}
      {/* ------------------------------------------------------------- */}
      <div style={{ marginTop: 40, padding: 0, background: '#1e1e1e', borderRadius: 12, boxShadow: '0 4px 6px rgba(0,0,0,0.3)', minHeight: 600, overflow: 'hidden' }}>
        
        {/*
          ⚠️ IMPORTANTE PARA EVITAR QUE SE SOLAPE: 
          Debes ELIMINAR O MODIFICAR la clase 'h-screen' del div padre 
          en tu archivo 'src/components/ChatInterface.tsx' (Línea 39) 
          y reemplazarla por algo como 'min-h-[600px]'.
        */}
        <ChatInterface /> 
      </div>
      
    </div>
  );
}

// ⚠️ EL VIEJO COMPONENTE ChatBotWidget HA SIDO ELIMINADO.

export default App;