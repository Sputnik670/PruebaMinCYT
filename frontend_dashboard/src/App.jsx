import { useState, useEffect } from 'react';
import { 
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer 
} from 'recharts';
import './App.css';

// --- PROCESADORES DE DATOS ---

const agregarDatosBitacora = (datos) => {
  if (!Array.isArray(datos) || datos.length === 0) return [];
  
  const agrupado = datos.reduce((acc, item) => {
    const duracion = parseFloat(item['Duración (hs)']) || 0; 
    const tipo = item['Tipo'];

    if (!acc[tipo]) {
      acc[tipo] = { name: tipo, horas: 0 };
    }
    acc[tipo].horas += duracion;
    return acc;
  }, {});

  return Object.values(agrupado);
};

// --- COMPONENTES VISUALES ---

function App() {
  const [bitacora, setBitacora] = useState([]);
  const [ventas, setVentas] = useState([]);
  const [tendencia, setTendencia] = useState([]); // Nuevo estado para el gráfico
  const [cargando, setCargando] = useState(true);

  const API_URL = import.meta.env.VITE_API_URL; 

  useEffect(() => {
    const baseUrl = API_URL || "http://127.0.0.1:8000";

    // Hacemos 3 peticiones ahora (incluyendo la tendencia limpia)
    Promise.all([
      fetch(`${baseUrl}/api/metricas`).then(res => res.json()),
      fetch(`${baseUrl}/api/ventas_crudas`).then(res => res.json()), // CORREGIDO: URL correcta
      fetch(`${baseUrl}/api/tendencia_inversion`).then(res => res.json()) // NUEVO: Datos limpios
    ])
    .then(([datosBitacora, datosVentas, datosTendencia]) => {
      setBitacora(datosBitacora);
      setVentas(datosVentas);
      setTendencia(datosTendencia);
      setCargando(false);
    })
    .catch((error) => {
      console.error("Error al conectar con la API:", error);
      setCargando(false);
    });
  }, [API_URL]);

  // Tabla genérica para mostrar datos crudos
  const TablaDinamica = ({ titulo, datos, color }) => {
    if (!datos || datos.length === 0 || datos.error) return <p>Sin datos para {titulo}.</p>;
    
    const columnas = Object.keys(datos[0]); 

    return (
      <section style={{ overflowX: 'auto' }}>
        <h2>{titulo}</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '10px', fontSize: '0.9em' }}>
          <thead>
            <tr style={{ backgroundColor: color, color: 'white', textAlign: 'left' }}>
              {columnas.map(col => <th key={col} style={{ padding: '10px' }}>{col}</th>)}
            </tr>
          </thead>
          <tbody>
            {datos.map((fila, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #ddd' }}>
                {columnas.map(col => (
                  <td key={col} style={{ padding: '10px' }}>{fila[col]}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    );
  };
    
  return (
    <div style={{ padding: '40px', fontFamily: 'Inter, Arial, sans-serif', maxWidth: '1200px', margin: '0 auto' }}>
      <header style={{ marginBottom: '40px' }}>
        <h1 style={{ borderBottom: '2px solid #333', paddingBottom: '10px' }}>🚀 Dashboard Maestro</h1>
        <p style={{ color: '#666' }}>Visualización de datos en tiempo real desde Google Sheets</p>
      </header>
      
      {cargando ? <div className="loader">Cargando datos del servidor...</div> : (
        <div style={{ display: 'grid', gap: '60px' }}>
          
          {/* --- SECCIÓN DE GRÁFICOS (KPIs) --- */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '20px' }}>
            
            {/* Gráfico 1: Barras de Bitácora */}
            <section style={{ border: '1px solid #eee', padding: '20px', borderRadius: '12px', boxShadow: '0 4px 6px rgba(0,0,0,0.05)' }}>
              <h2 style={{marginTop: 0}}>⏱️ Horas por Tipo de Tarea</h2>
              <div style={{ width: '100%', height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={agregarDatosBitacora(bitacora)}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="horas" fill="#3498db" name="Horas" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>

            {/* Gráfico 2: Línea de Tendencia de Ventas (NUEVO) */}
            <section style={{ border: '1px solid #eee', padding: '20px', borderRadius: '12px', boxShadow: '0 4px 6px rgba(0,0,0,0.05)' }}>
              <h2 style={{marginTop: 0}}>💰 Evolución de Inversión</h2>
              <div style={{ width: '100%', height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={tendencia}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="Fecha" />
                    <YAxis />
                    <Tooltip formatter={(value) => `$ ${value.toLocaleString()}`} />
                    <Legend />
                    <Line type="monotone" dataKey="Venta" stroke="#27ae60" strokeWidth={3} name="Monto ($)" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>

          </div>

          {/* --- SECCIÓN DE TABLAS DETALLADAS --- */}
          <div style={{ display: 'grid', gap: '40px' }}>
            <TablaDinamica 
                titulo="📅 Bitácora Detallada"
                datos={bitacora}
                color="#2c3e50" 
            />
            
            <TablaDinamica 
                titulo="📋 Proyectos y Ventas (Crudo)"
                datos={ventas}
                color="#e74c3c" 
            />
          </div>

        </div>
      )}
    </div>
  );
}

export default App;