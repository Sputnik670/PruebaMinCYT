import { useState, useEffect } from 'react';
import { 
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer 
} from 'recharts';
import './App.css';

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // URL FIJA DE RENDER (Sin el guion extra)
  const API_URL = "https://pruebamincyt.onrender.com";

  useEffect(() => {
    console.log("📡 Conectando al nuevo backend...");
    
    // Hacemos UNA sola petición al endpoint maestro
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
        console.error("❌ Error fatal:", err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  // --- PROCESAMIENTO LOCAL SIMPLE ---
  // Preparamos los datos de bitácora para el gráfico de barras
  const prepararBitacora = () => {
    if (!data?.bitacora) return [];
    const conteo = {};
    data.bitacora.forEach(row => {
      const tipo = row['Tipo'] || 'Otros';
      // Intentamos leer 'Duración (hs)' o 'Duracion', si falla es 1 hora por defecto
      const horas = parseFloat(row['Duración (hs)'] || row['Duracion']) || 0;
      
      // --- CORRECCIÓN AQUÍ ---
      // Antes decía: +Hs (Error) -> Ahora dice: +horas (Correcto)
      conteo[tipo] = (conteo[tipo] || 0) + horas;
    });
    return Object.keys(conteo).map(k => ({ name: k, horas: conteo[k] }));
  };

  // --- RENDERIZADO ---

  if (loading) return (
    <div style={{display:'flex', justifyContent:'center', alignItems:'center', height:'100vh'}}>
      <h2>⏳ Cargando datos del sistema...</h2>
    </div>
  );

  if (error) return (
    <div style={{color: 'red', padding: 50, textAlign: 'center'}}>
      <h1>⚠️ Error de Conexión</h1>
      <p>{error}</p>
      <p>Verifica que el backend en Render haya terminado el deploy.</p>
    </div>
  );

  return (
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
        
        {/* GRÁFICO 1: BARRAS (BITÁCORA) */}
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

        {/* GRÁFICO 2: LÍNEAS (DINERO) */}
        <div style={{ background: '#1e1e1e', padding: '20px', borderRadius: '15px' }}>
          <h3 style={{ color: 'white' }}>💰 Tendencia de Inversión</h3>
          <div style={{ height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.tendencia_grafico}>
                <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                <XAxis dataKey="fecha" stroke="#ccc" />
                <YAxis stroke="#ccc" />
                <Tooltip 
                  contentStyle={{backgroundColor: '#333', border: 'none'}}
                  formatter={(val) => `$ ${val.toLocaleString()}`}
                />
                <Line type="monotone" dataKey="monto" stroke="#82ca9d" strokeWidth={3} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* TABLA DE DATOS CRUDOS (DEBUG) */}
      <div style={{ marginTop: '50px' }}>
        <h3>📋 Datos Recibidos (Últimos 5 registros de Ventas)</h3>
        <div style={{ overflowX: 'auto', background: '#2a2a2a', padding: '20px', borderRadius: '10px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', color: '#ccc' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #555', textAlign:'left' }}>
                {data.ventas_tabla.length > 0 && Object.keys(data.ventas_tabla[0]).map(k => (
                  <th key={k} style={{ padding: 10 }}>{k}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.ventas_tabla.slice(0, 5).map((row, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #444' }}>
                  {Object.values(row).map((val, j) => (
                    <td key={j} style={{ padding: 10 }}>{val}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default App;