import { createClient } from '@supabase/supabase-js'

// Reemplaza esto con TU URL y TU KEY de Supabase (las encuentras en Settings > API)
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://bqkltwwgaipldcgmwtna.supabase.co'
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJxa2x0d3dnYWlwbGRjZ213dG5hIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjM5MjMwMDYsImV4cCI6MjA3OTQ5OTAwNn0.FWEoemrxWpG3MMnSsGkPaNbVv7ZJKPx-HQZ1uH-PCpE'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)