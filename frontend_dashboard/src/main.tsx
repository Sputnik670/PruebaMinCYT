import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx' // <--- IMPORTACIÓN CORREGIDA A .tsx
// 👇 ESTA LÍNEA ES LA CLAVE PARA QUE SE VEA EL DISEÑO
import './index.css' 
// 👇 Mantine (si lo usas, mal no hace dejarlo)
import '@mantine/core/styles.css'; 
import { MantineProvider } from '@mantine/core';

ReactDOM.createRoot(document.getElementById('root')!).render( // Agregado '!' para TypeScript
  <React.StrictMode>
    <MantineProvider>
      <App />
    </MantineProvider>
  </React.StrictMode>,
)