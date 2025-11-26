// src/vite-env.d.ts

/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_GOOGLE_API_KEY: string
  readonly VITE_BACKEND_URL: string // <--- AÑADIMOS NUESTRA VARIABLE DE BACKEND
  // Puedes añadir aquí otras variables VITE_... si las usas
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}