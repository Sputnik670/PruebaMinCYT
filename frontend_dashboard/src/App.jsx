// Ignoramos la variable de entorno por ahora para probar directo
  // const API_URL = import.meta.env.VITE_API_URL; 

  useEffect(() => {
    // URL FIJA DE RENDER (La "quemamos" aquí para asegurar conexión)
    const baseUrl = "https://prueba-mincyt.onrender.com"; 

    console.log("📡 Intentando conectar a:", baseUrl);

    Promise.all([
      fetch(`${baseUrl}/api/metricas`).then(res => {
          if (!res.ok) throw new Error("Error en Metricas");
          return res.json();
      }),
      fetch(`${baseUrl}/api/ventas_crudas`).then(res => {
          if (!res.ok) throw new Error("Error en Ventas");
          return res.json();
      }),
      fetch(`${baseUrl}/api/tendencia_inversion`).then(res => {
          if (!res.ok) throw new Error("Error en Tendencia");
          return res.json();
      })
    ])
    .then(([datosBitacora, datosVentas, datosTendencia]) => {
      console.log("✅ Datos Recibidos Bitácora:", datosBitacora);
      console.log("✅ Datos Recibidos Tendencia:", datosTendencia);
      
      setBitacora(datosBitacora);
      setVentas(datosVentas);
      setTendencia(datosTendencia);
      setCargando(false);
    })
    .catch((error) => {
      console.error("❌ ERROR CRÍTICO AL PEDIR DATOS:", error);
      setCargando(false);
    });
  }, []);