import { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [data, setData] = useState([]);
  const [syncing, setSyncing] = useState(false);
  const [verTodos, setVerTodos] = useState(false); // Estado para desplegar tabla
  
  // Tu URL de Render
  const API_URL = "https://pruebamincyt.onrender.com";

  // Cargar datos
  const cargarDatos = () => {
    fetch(`${API_URL}/api/data`)
      .then(res => {
        if (!res.ok) throw new Error(`Error servidor: ${res.status}`);
        return res.json();
      })
      .then(setData)
      .catch(console.error);
  };

  useEffect(() => { cargarDatos(); }, []);

  // Sincronizar
  const sincronizar = async () => {
    setSyncing(true);
    try {
      const res = await fetch(`${API_URL}/api/sync`, { method: 'POST' });
      const json = await res.json();
      if(json.status === 'error') throw new Error(json.msg);
      
      alert(json.msg || "¡Sincronización exitosa!");
      cargarDatos(); 
    } catch (e) { 
      alert("Error al sincronizar: " + e.message); 
    }