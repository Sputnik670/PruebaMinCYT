import React from 'react';
import { FileText, Calendar, Clock, Download } from 'lucide-react';

export const MeetingHistory: React.FC = () => {
  // Datos de ejemplo para que la interfaz no se vea vacía por ahora
  const historialEjemplo = [
    { id: 1, titulo: "Reunión de Planificación", fecha: "2023-10-27", hora: "10:00 AM", resumen: "Se definieron los objetivos del Q4..." },
    { id: 2, titulo: "Revisión de Presupuesto", fecha: "2023-10-26", hora: "14:30 PM", resumen: "Aprobación de partidas presupuestarias..." },
  ];

  return (
    <div className="space-y-4">
      {historialEjemplo.map((acta) => (
        <div key={acta.id} className="bg-white/5 border border-white/10 rounded-xl p-4 hover:bg-white/10 transition-colors">
          <div className="flex justify-between items-start mb-2">
            <h3 className="text-slate-200 font-semibold flex items-center gap-2">
              <FileText size={18} className="text-blue-400" />
              {acta.titulo}
            </h3>
            <span className="text-xs text-slate-500 bg-black/30 px-2 py-1 rounded border border-white/5">
                ID: {acta.id}
            </span>
          </div>
          
          <p className="text-slate-400 text-sm mb-4 line-clamp-2">{acta.resumen}</p>
          
          <div className="flex items-center justify-between border-t border-white/5 pt-3 mt-3">
             <div className="flex gap-4 text-xs text-slate-500">
                <span className="flex items-center gap-1"><Calendar size={12}/> {acta.fecha}</span>
                <span className="flex items-center gap-1"><Clock size={12}/> {acta.hora}</span>
             </div>
             {/* CORRECCIÓN AQUÍ: Se agregaron title y aria-label */}
             <button 
                className="text-blue-400 hover:text-blue-300 transition-colors"
                title="Descargar acta"
                aria-label="Descargar acta"
             >
                <Download size={16} />
             </button>
          </div>
        </div>
      ))}
      
      <div className="text-center p-4 text-xs text-slate-600">
        No hay más registros históricos disponibles.
      </div>
    </div>
  );
};