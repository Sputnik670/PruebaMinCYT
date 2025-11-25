import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'mask-icon.svg'],
      manifest: {
        name: 'Dashboard MinCYT',
        short_name: 'MinCYT Dash',
        description: 'Dashboard de Gestión Inteligente con IA',
        theme_color: '#1a1a1a',
        background_color: '#1a1a1a',
        display: 'standalone', // Esto hace que parezca una App nativa
        icons: [
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png'
          }
        ]
      }
    })
  ],
  // --- AGREGADO: Configuración para desarrollo Local ---
  server: {
    port: 5173, // Puerto estándar de Vite
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000', // Apunta a tu backend local si lo corres en tu PC
        changeOrigin: true,
        secure: false,
      }
    }
  }
})