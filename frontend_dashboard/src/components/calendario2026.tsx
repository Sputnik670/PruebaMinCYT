import React from 'react';
import { Calendar, AlertCircle } from 'lucide-react';

interface AgendaTableProps {
  title: string;
  color: 'blue' | 'green' | 'purple';
  data: any[];
  isLoading: boolean;
}

export const AgendaTable: React.FC<AgendaTableProps> = ({ title, color, data, isLoading }) => {
  
  // Configuración de colores dinámica
  const colorStyles = {
    blue: { header: 'bg-blue-900 text-blue-100', icon: 'text-blue-400', border: 'border-blue-200' },
    green: { header: 'bg-emerald-900 text-emerald-100', icon: 'text-emerald-400', border: 'border-emerald-200' },
    purple: { header: 'bg-purple-900 text-purple-100', icon: 'text-purple-400', border: 'border-purple-200' },
  };

  const style = colorStyles[color];
  const columnas = data.length > 0 ? Object.keys(data[0]) : [];

  if (isLoading) {
    return (
      <div className="animate-pulse bg-white rounded-xl p-6 shadow-lg border border-slate-200 h-64 flex items-center justify-center">
         <span className="text-slate-400">Cargando agenda...</span>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="bg-white rounded-xl p-6 shadow-lg border border-slate-200 h-64 flex flex-col items-center justify-center text-slate-400 gap-2">
         <AlertCircle size={24} />
         <p>No hay datos disponibles</p>
      </div>
    );
  }

  return (
    <div className={`bg-white rounded-xl shadow-lg border ${style.border} overflow-hidden flex flex-col h-full`}>
      <div className={`${style.header} p-3 flex items-center gap-2 font-bold`}>
        <Calendar size={18} className={style.icon} />
        {title}
      </div>
      
      <div className="overflow-auto flex-1 scrollbar-thin scrollbar-thumb-slate-300">
        <table className="w-full text-sm text-left">
          <thead className="text-xs uppercase bg-slate-50 text-slate-500 sticky top-0">
            <tr>
              {columnas.map((col) => (
                <th key={col} className="px-4 py-2 border-b font-semibold">{col}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-600">
            {data.map((row, i) => (
              <tr key={i} className="hover:bg-slate-50/80 transition-colors">
                {columnas.map((col) => (
                  <td key={`${i}-${col}`} className="px-4 py-2 whitespace-nowrap">
                    {row[col] ? row[col].toString().substring(0, 30) + (row[col].toString().length > 30 ? '...' : '') : '-'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="bg-slate-50 p-2 text-right text-[10px] text-slate-400 border-t">
        {data.length} registros encontrados
      </div>
    </div>
  );
};