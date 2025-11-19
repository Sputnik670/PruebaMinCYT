import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'; // <--- NUEVO
import './App.css'
// ...
// Función auxiliar para agregar las horas de la Bitácora
const agregarDatosBitacora = (datos) => {
  const agrupado = datos.reduce((acc, item) => {
    // Tomamos la duración (ya sabemos que es un string, lo convertimos a número)
    const duracion = parseFloat(item['Duración (hs)']); 
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
  const [bitacora, setBitacora] = useState([])
  const [ventas, setVentas] = useState([])
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    // Hacemos las dos peticiones en paralelo
    Promise.all([
      fetch("http://127.0.0.1:8000/api/metricas").then(res => res.json()),
      fetch("http://127.0.0.1:8000/api/ventas").then(res => res.json())
    ])
    .then(([datosBitacora, datosVentas]) => {
      setBitacora(datosBitacora)
      setVentas(datosVentas)
      setCargando(false)
    })
    .catch((error) => {
      console.error("Error:", error)
      setCargando(false)
    });
  }, [])

  // Función auxiliar para renderizar tablas dinámicas (útil para Ventas)
  const TablaDinamica = ({ datos }) => {
    if (datos.length === 0) return <p>No hay datos para mostrar.</p>;
    
    const columnas = Object.keys(datos[0]); // Detecta columnas automáticamente

    return (
      <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '10px', fontSize: '0.9em' }}>
        <thead>
          <tr style={{ backgroundColor: '#e74c3c', color: 'white', textAlign: 'left' }}> {/* Color Rojo para Ventas */}
            {columnas.map(col => <th key={col} style={{ padding: '10px' }}>{col}</th>)}
          </tr>
        </thead>
        <tbody>
          {datos.map((fila, i) => (
            <tr key={i} style={{ borderBottom: '1px solid #ddd' }}>
              {columnas.map(col => <td key={col} style={{ padding: '10px' }}>{fila[col]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  return (
    <div style={{ padding: '40px', fontFamily: 'Arial, sans-serif', maxWidth: '1200px', margin: '0 auto' }}>
      <h1 style={{ borderBottom: '2px solid #333', paddingBottom: '10px' }}>🚀 Dashboard Maestro</h1>
      
      {cargando ? <p>Cargando datos...</p> : (
        <div style={{ display: 'grid', gap: '40px' }}>
          
          {/* SECCIÓN 1: BITÁCORA (Tabla manual personalizada) */}
          <section>
    <h2>📅 Bitácora de Impacto (Horas por Tipo)</h2>
    {/* Usamos el componente de Recharts para visualizar */}
    <div style={{ width: '100%', height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
            <BarChart
                data={agregarDatosBitacora(bitacora)} // Usamos los datos agregados
                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis label={{ value: 'Horas', angle: -90, position: 'insideLeft' }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="horas" fill="#3498db" name="Horas Invertidas" />
            </BarChart>
        </ResponsiveContainer>
    </div>

    {/* Aquí puedes volver a pegar la tabla antigua si quieres ver el detalle crudo */}
</section>

          {/* SECCIÓN 2: VENTAS (Tabla automática) */}
          <section>
            <h2>💰 Ventas y Finanzas</h2>
            {/* Aquí usamos el componente dinámico para que se adapte a tus columnas */}
            <TablaDinamica datos={ventas} />
          </section>

        </div>
      )}
    </div>
  )
}

export default App