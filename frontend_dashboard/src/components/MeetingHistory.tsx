import { useEffect, useState } from 'react';
import { FileText, Calendar, Clock, Download, Loader2, Trash2 } from 'lucide-react';

// Recibimos el trigger para recargar la lista
export const MeetingHistory = ({ refreshTrigger }: { refreshTrigger: number }) => {
  const [actas, setActas] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const rawUrl = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
  const API_URL = rawUrl.replace(/\/api\/?$/, "").replace(/\/$/, "");

  const fetchHistorial = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/actas`); 
      if (response.ok) {
        const data = await response.json();
        setActas(data);
      } else {
        console.error("Error al cargar historial");
      }
    } catch (error) {
      console.error("Error de red:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistorial();
  }, [refreshTrigger]);

  const borrarActa = async (id: number) => {
      if(!confirm("¿Seguro que deseas eliminar esta acta?")) return;
      try {
          await fetch(`${API_URL}/actas/${id}`, { method: 'DELETE' });
          fetchHistorial(); 
      } catch (e) {
          console.error(e);
      }
  }

  // --- NUEVA FUNCIÓN DE DESCARGA ---
  const descargarActa = (acta: any) => {
    try {
        // 1. Preparamos el contenido del archivo
        const contenido = [
            "========================================",
            `TITULO: ${acta.titulo || "Reunión sin título"}`,
            `FECHA: ${new Date(acta.created_at).toLocaleString()}`,
            "========================================",
            "\n--- RESUMEN IA ---",
            acta.resumen_ia || "No disponible",
            "\n--- TRANSCRIPCIÓN COMPLETA ---",
            acta.transcripcion || ""
        ].join("\n");

        // 2. Creamos un 'Blob' (un archivo en memoria)
        const blob = new Blob([contenido], { type: 'text/plain' });
        
        // 3. Creamos un enlace temporal para forzar la descarga
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        // Nombre del archivo: Acta-ID-Fecha.txt
        a.download = `Acta-${acta.id}-${new Date(acta.created_at).toISOString().split('T')[0]}.txt`;
        
        document.body.appendChild(a);
        a.click();
        
        // 4. Limpieza
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error("Error al descargar:", error);
        alert("No se pudo generar el archivo de descarga.");
    }
  };

  if (loading && actas.length === 0) {
    return (
        <div className="flex justify-center items-center h-40 text-slate-400">
            <Loader2 className="animate-spin mr-2" /> Cargando historial...
        </div>
    );
  }

  return (
    <div className="space-y-4">
      {actas.length === 0 ? (
          <div className="text-center text-slate-500 py-10">
              No hay actas grabadas aún.
          </div>
      ) : (
          actas.map((acta: any) => (
            <div key={acta.id} className="bg-white/5 border border-white/10 rounded-xl p-4 hover:bg-white/10 transition-colors group">
              <div className="flex justify-between items-start mb-2">
                <h3 className="text-slate-200 font-semibold flex items-center gap-2">
                  <FileText size={18} className="text-blue-400" />
                  {acta.titulo || "Reunión sin título"}
                </h3>
                <div className="flex gap-2">
                    <span className="text-xs text-slate-500 bg-black/30 px-2 py-1 rounded border border-white/5">
                    ID: {acta.id}
                    </span>
                    <button 
                        onClick={() => borrarActa(acta.id)}
                        className="text-slate-600 hover:text-red-400 transition-colors"
                        title="Borrar"
                    >
                        <Trash2 size={14} />
                    </button>
                </div>
              </div>
              
              <p className="text-slate-400 text-sm mb-4 line-clamp-2">
                  {acta.resumen_ia || acta.transcripcion?.substring(0, 100) + "..."}
              </p>
              
              <div className="flex items-center justify-between border-t border-white/5 pt-3 mt-3">
                  <div className="flex gap-4 text-xs text-slate-500">
                    <span className="flex items-center gap-1">
                        <Calendar size={12}/> 
                        {new Date(acta.created_at).toLocaleDateString()}
                    </span>
                    <span className="flex items-center gap-1">
                        <Clock size={12}/> 
                        {new Date(acta.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                    </span>
                  </div>
                  
                  {/* BOTÓN DE DESCARGA CONECTADO */}
                  <button 
                    onClick={() => descargarActa(acta)}
                    className="text-blue-400 hover:text-blue-300 transition-colors"
                    title="Descargar acta"
                    aria-label="Descargar acta"
                  >
                    <Download size={16} />
                  </button>
              </div>
            </div>
          ))
      )}
      
      {actas.length > 0 && (
        <div className="text-center p-4 text-xs text-slate-600">
            Mostrando los últimos registros.
        </div>
      )}
    </div>
  );
};