import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './App.css';

// Función auxiliar para agregar las horas de la Bitácora
const agregarDatosBitacora = (datos) => {
  // Manejamos el caso donde los datos son un objeto de error (si falla la API)
  if (!Array.isArray(datos) || datos.length === 0) return [];
    
  const agrupado = datos.reduce((acc, item) => {
    // Tomamos la duración. Si no es un número válido, usamos 0.
    const duracion = parseFloat(item['Duración (hs)']) || 0; 
    const tipo = item['Tipo'];

    if (!acc[tipo]) {
      acc[tipo] = { name: tipo, horas: 0 };
    }
    acc[tipo].horas += duracion;
    return acc;
  }, {});

  // Convertimos el objeto en un array que Recharts pueda leer
  return Object.values(agrupado);
};

function App() {
  const [bitacora, setBitacora] = useState([]);
  const [ventas, setVentas] = useState([]);
  const [cargando, setCargando] = useState(true);

  // Leemos la URL de la API desde la variable de entorno de Vercel/Vite
  const API_URL = import.meta.env.VITE_API_URL; 
  // NOTA: Si esta variable no está seteada, por defecto usará localhost.

  useEffect(() => {
    // Si la URL es indefinida (solo en desarrollo y no configurado), usamos la local
    const baseUrl = API_URL || "http://127.0.0.1:8000";

    // Hacemos las dos peticiones en paralelo
    Promise.all([
      fetch(`${baseUrl}/api/metricas`).then(res => res.json()),
      fetch(`${baseUrl}/api/ventas`).then(res => res.json())
    ])
    .then(([datosBitacora, datosVentas]) => {
      setBitacora(datosBitacora);
      setVentas(datosVentas);
      setCargando(false);
    })
    .catch((error) => {
      console.error("Error al conectar con la API:", error);
      setCargando(false);
    });
  }, [API_URL]);

  // Función auxiliar para renderizar tablas dinámicas (útil para Ventas)
  const TablaDinamica = ({ titulo, datos, color }) => {
    if (datos.length === 0 || datos.error) return <p>No hay datos disponibles para {titulo}.</p>;
    
    // Filtramos para obtener solo las claves (nombres de columnas)
    const columnas = Object.keys(datos[0]); 

    return (
        <section>
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
                                <td key={col} style={{ padding: '10px' }}>
                                    {fila[col]}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </section>
    );
  };
    
  // Componente de la Bitácora personalizada
  const TablaBitacora = () => {
    if (bitacora.length === 0 || bitacora.error) return <p>No hay datos de Bitácora para mostrar.</p>;

    return (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '10px' }}>
            <thead>
                <tr style={{ backgroundColor: '#2c3e50', color: 'white', textAlign: 'left' }}>
                    <th style={{ padding: '12px' }}>Fecha</th>
                    <th style={{ padding: '12px' }}>Tipo</th>
                    <th style={{ padding: '12px' }}>Cliente</th>
                    <th style={{ padding: '12px' }}>Duración</th>
                    <th style={{ padding: '12px' }}>Detalles</th>
                </tr>
            </thead>
            <tbody>
                {bitacora.map((fila, index) => (
                    <tr key={index} style={{ borderBottom: '1px solid #ddd' }}>
                        {/* Solución al Invalid Date: Mostramos el string tal cual, cortando la hora */}
                        <td style={{ padding: '10px' }}>{fila['Fecha'] ? fila['Fecha'].split(' ')[0] : '-'}</td>
                        <td style={{ padding: '10px', fontWeight: 'bold' }}>{fila['Tipo']}</td>
                        <td style={{ padding: '10px' }}>{fila['Título / Cliente']}</td>
                        <td style={{ padding: '10px' }}>{fila['Duración (hs)']} hs</td>
                        <td style={{ padding: '10px', color: '#666' }}>{fila['Detalles/Log']}</td>
                    </tr>
                ))}
            </tbody>
        </table>
    );
  };


  return (
    <div style={{ padding: '40px', fontFamily: 'Inter, Arial, sans-serif', maxWidth: '1200px', margin: '0 auto' }}>
      <h1 style={{ borderBottom: '2px solid #333', paddingBottom: '10px' }}>🚀 Dashboard Maestro</h1>
      
      {cargando ? <p>Cargando datos...</p> : (
        <div style={{ display: 'grid', gap: '40px' }}>
          
          {/* GRÁFICO DE BARRAS DE BITÁCORA */}
          <section>
            <h2>📈 Distribución de Horas por Tipo</h2>
            <div style={{ width: '100%', height: 350, border: '1px solid #ddd', padding: '10px', borderRadius: '8px' }}>
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                        data={agregarDatosBitacora(bitacora)}
                        margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                    >
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis label={{ value: 'Horas', angle: -90, position: 'insideLeft' }} />
                        <Tooltip />
                        <Legend />
                        <Bar dataKey="horas" fill="#3498db" name="Horas Invertidas" radius={[10, 10, 0, 0]} />
                    </BarChart>
                </ResponsiveContainer>
            </div>
          </section>

          
          {/* BLOQUE DE TABLAS */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '40px' }}>
            
            {/* TABLA DE BITÁCORA CRUDA */}
            <section>
                <h2 style={{marginTop: '0'}}>📅 Detalles de Bitácora (Tiempo)</h2>
                <TablaBitacora />
            </section>
            
            {/* TABLA DE VENTAS CRUDA */}
            <TablaDinamica 
                titulo="💰 Detalles de Ventas (Finanzas)"
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