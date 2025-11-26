// src/vite-env.d.ts

/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_GOOGLE_API_KEY: string
  // Puedes añadir aquí otras variables VITE_... si las usas
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}