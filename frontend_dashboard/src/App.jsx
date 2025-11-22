import { useState, useEffect } from 'react';
import { 
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer 
} from 'recharts';
import './App.css';

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // 1. URL CORRECTA (Backend)
  const API_URL = "https://pruebamincyt.onrender.com";

  useEffect(() => {
    console.log("📡 Conectando...");
    fetch(`${API_URL}/api/dashboard`)
      .then(res => {
        if (!res.ok) throw new Error(`Error HTTP: ${res.status}`);
        return res.json();
      })
      .then(resultado => {
        console.log("✅ Datos recibidos:", resultado);
        setData(resultado);
        setLoading(false);
      })
      .catch(err => {
        console.error("❌ Error:", err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // 2. PROCESAMIENTO DE BITÁCORA (Corrección Hs -> horas)
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

  // 3. ESTILOS Y RENDERIZADO
  if (loading) return <div style={{display:'flex', height:'100vh', alignItems:'center', justifyContent:'center'}}><h2>⏳ Cargando...</h2></div>;
  if (error) return <div style={{color:'red', padding:50, textAlign:'center'}}><h1>⚠️ Error</h1><p>{error}</p></div>;

  return (
    // 4. SCROLL HABILITADO (minHeight + overflow)
    <div style={{ 
      maxWidth: '1200px', 
      margin: '0 auto', 
      padding: '20px', 
      fontFamily: 'Arial, sans-serif',
      minHeight: '100vh',
      overflowY: 'auto'
    }}>
      <header style={{ textAlign: 'center', marginBottom: '50px' }}>
        <h1 style={{ fontSize: '2.5rem' }}>🚀 Dashboard Maestro V2</h1>
        <p style={{ color: '#666' }}>Conexión Directa a Google Sheets</p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '30px' }}>
        
        {/* Gráfico 1 */}
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

        {/* Gráfico 2 */}
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

      {/* Tabla Original */}
      <div style={{ marginTop: '50px' }}>
        <h3>📋 Registros de Ventas</h3>
        <TablaGenerica datos={data.ventas_tabla} />
      </div>

      {/* 5. LA NUEVA TABLA QUE FALTABA */}
      <div style={{ marginTop: '50px', marginBottom: '100px' }}>
        <h3 style={{ color: '#3498db' }}>📂 Datos Adicionales (Nueva Integración)</h3>
        {data.extra_tabla && data.extra_tabla.length > 0 ? (
          <TablaGenerica datos={data.extra_tabla} />
        ) : (
          <p style={{ color: '#666', fontStyle: 'italic' }}>
            Esperando datos... (Verifica el link en el backend si esto no cambia)
          </p>
        )}
      </div>

    </div>
  );
}

// Componente para Tablas
const TablaGenerica = ({ datos }) => {
  if (!datos || datos.length === 0) return <p>Sin datos.</p>;
  // Tomamos las columnas del primer objeto
  const columnas = Object.keys(datos[0]);

  return (
    <div style={{ overflowX: 'auto', background: '#2a2a2a', padding: '20px', borderRadius: '10px' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', color: '#ccc', minWidth: '600px' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #555', textAlign:'left' }}>
            {columnas.map(k => (
              <th key={k} style={{ padding: 10, color: '#fff' }}>{k}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {datos.slice(0, 10).map((row, i) => (
            <tr key={i} style={{ borderBottom: '1px solid #444' }}>
              {columnas.map((col, j) => (
                <td key={j} style={{ padding: 10 }}>{row[col]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {datos.length > 10 && <p style={{marginTop: 10, fontSize: '0.8em'}}>... mostrando 10 de {datos.length} filas.</p>}
    </div>
  );
};

export default App;