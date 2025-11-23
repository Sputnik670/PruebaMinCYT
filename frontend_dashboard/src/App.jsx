// ... imports igual que antes ...

function App() {
  // ... estados ...
  const [syncing, setSyncing] = useState(false); // Nuevo estado para loading del botón

  // Función para llamar al puente
  const sincronizarDatos = async () => {
    setSyncing(true);
    try {
      const res = await fetch(`${API_URL}/api/sync`, { method: 'POST' });
      const data = await res.json();
      alert("Sincronización completa:\n" + data.detalles.join("\n"));
      window.location.reload(); // Recargar para ver los datos nuevos
    } catch (e) {
      alert("Error al sincronizar: " + e.message);
    } finally {
      setSyncing(false);
    }
  };

  // ... resto del código igual ...

  return (
    <div className="dashboard-container">
      <header style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom: '40px' }}>
        <div>
            <h1 style={{ fontSize: '2.5rem', margin:0 }}>🚀 Dashboard MinCYT</h1>
            <p style={{ color: '#888', margin:0 }}>Datos en Vivo</p>
        </div>
        
        {/* BOTÓN MÁGICO */}
        <button 
            onClick={sincronizarDatos} 
            disabled={syncing}
            style={{
                background: syncing ? '#555' : '#2ecc71',
                border: 'none', padding: '10px 20px', color: 'white', 
                borderRadius: '8px', cursor: syncing ? 'wait' : 'pointer',
                fontWeight: 'bold', fontSize: '1rem'
            }}
        >
            {syncing ? '🔄 Sincronizando...' : '☁️ Actualizar Datos'}
        </button>
      </header>

      {/* ... Resto de gráficos y tablas ... */}