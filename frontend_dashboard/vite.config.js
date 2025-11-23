import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate', // Se actualiza sola cuando subes cambios
      includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'mask-icon.svg'],
      manifest: {
        name: 'Dashboard MinCYT', // Nombre largo (Splash screen)
        short_name: 'MinCYT Dash', // Nombre corto (Icono en escritorio)
        description: 'Dashboard de Gestión Inteligente con IA',
        theme_color: '#1a1a1a', // Color de la barra de estado
        background_color: '#1a1a1a', // Color de fondo al abrir
        display: 'standalone', // Modo "App" (sin barra de navegador)
        icons: [
          {
            src: 'pwa-192x192.png', // Icono mediano
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: 'pwa-512x512.png', // Icono grande
            sizes: '512x512',
            type: 'image/png'
          },
          {
            src: 'pwa-512x512.png', // Icono máscara (para Android modernos)
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable'
          }
        ]
      }
    })
  ],
})