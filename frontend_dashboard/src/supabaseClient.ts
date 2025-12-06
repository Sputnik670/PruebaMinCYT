import { createClient } from '@supabase/supabase-js'

// 🛡️ CORRECCIÓN DE SEGURIDAD:
// Eliminamos el fallback hardcodeado. Ahora solo confía en las variables de entorno.
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error("❌ Faltan las variables de entorno VITE_SUPABASE_URL o VITE_SUPABASE_ANON_KEY");
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)