import { useState, useEffect } from 'react';
import { 
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer 
} from 'recharts';
import './App.css';

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
        <p style={{ color: '#666' }}>Gestión y Calendario</p>
      </header>

      {/* GRÁFICOS (Siempre visibles) */}
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

      {/* --- ACORDEÓN 1: VENTAS --- */}
      <SeccionAcordeon titulo="📋 Registros de Ventas (Histórico)" defaultAbierto={false}>
        <TablaGenerica datos={data.ventas_tabla} filasPorPagina={5} />
      </SeccionAcordeon>

      {/* --- ACORDEÓN 2: CALENDARIO (Antes Datos Extra) --- */}
      <SeccionAcordeon titulo="📅 Calendario Internacionales" defaultAbierto={true}>
        {data.extra_tabla && data.extra_tabla.length > 0 ? (
          <TablaGenerica datos={data.extra_tabla} filasPorPagina={10} />
        ) : (
          <p style={{ color: '#666', fontStyle: 'italic' }}>Sin datos disponibles.</p>
        )}
      </SeccionAcordeon>

    </div>
  );
}

// --- COMPONENTE ACORDEÓN (Reutilizable) ---
const SeccionAcordeon = ({ titulo, children, defaultAbierto = false }) => {
  const [abierto, setAbierto] = useState(defaultAbierto);

  return (
    <div style={{ marginBottom: '20px', borderRadius: '10px', overflow: 'hidden', border: '1px solid #333' }}>
      <button 
        onClick={() => setAbierto(!abierto)}
        style={{
          width: '100%', background: '#2c3e50', color: 'white', padding: '15px 20px',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          border: 'none', cursor: 'pointer', fontSize: '1.1rem', fontWeight: 'bold', textAlign: 'left'
        }}
      >
        <span>{titulo}</span>
        <span style={{ transform: abierto ? 'rotate(180deg)' : 'rotate(0deg)', transition: '0.3s' }}>▼</span>
      </button>
      {abierto && <div style={{ padding: '20px', background: '#1a1a1a' }}>{children}</div>}
    </div>
  );
};

// --- COMPONENTE TABLA CON PAGINACIÓN ---
const TablaGenerica = ({ datos, filasPorPagina = 10 }) => {
  const [paginaActual, setPaginaActual] = useState(1);
  if (!datos || datos.length === 0) return <p>Sin datos.</p>;
  
  const totalPaginas = Math.ceil(datos.length / filasPorPagina);
  const indiceUltimo = paginaActual * filasPorPagina;
  const indicePrimero = indiceUltimo - filasPorPagina;
  const datosVisibles = datos.slice(indicePrimero, indiceUltimo);
  const columnas = Object.keys(datos[0]);
  
  const cambiarPagina = (nuevaPagina) => {
    if (nuevaPagina >= 1 && nuevaPagina <= totalPaginas) setPaginaActual(nuevaPagina);
  };

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