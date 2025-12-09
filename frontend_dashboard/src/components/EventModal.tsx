import { X, Calendar, MapPin, DollarSign, FileText, Users, Building, Globe, Briefcase } from 'lucide-react';
import { AgendaItem } from '../types/types';

interface EventModalProps {
  isOpen: boolean;
  onClose: () => void;
  event: AgendaItem | null;
}

export const EventModal = ({ isOpen, onClose, event }: EventModalProps) => {
  if (!isOpen || !event) return null;

  // Formateadores
  const formatDate = (dateStr: string) => {
    if (!dateStr) return 'Fecha no definida';
    const date = new Date(dateStr + 'T12:00:00');
    return date.toLocaleDateString('es-AR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  };

  const formatMoney = (amount: number | undefined, currency: string | undefined) => {
    if (amount === undefined || amount === 0) return 'Sin costo registrado';
    return new Intl.NumberFormat('es-AR', { style: 'currency', currency: currency || 'ARS' }).format(amount);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl overflow-hidden animate-in zoom-in-95 duration-200">
        
        {/* HEADER */}
        <div className="bg-slate-50 px-6 py-4 border-b border-slate-200 flex justify-between items-start">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${
                event.ambito === 'Internacional' 
                  ? 'bg-purple-100 text-purple-700 border-purple-200' 
                  : 'bg-blue-100 text-blue-700 border-blue-200'
              }`}>
                {event.ambito || 'General'}
              </span>
              {event.num_expediente && (
                <span className="text-xs font-mono text-slate-500 bg-slate-200 px-2 py-0.5 rounded">
                  EXP: {event.num_expediente}
                </span>
              )}
            </div>
            <h2 className="text-xl font-bold text-slate-800 leading-tight">{event.titulo}</h2>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-200 rounded-full transition-colors text-slate-500">
            <X size={20} />
          </button>
        </div>

        {/* BODY */}
        <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
          
          {/* Grid Principal */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <Calendar className="text-blue-500 mt-1" size={18} />
                <div>
                  <p className="text-xs text-slate-500 font-semibold uppercase">Fecha</p>
                  <p className="text-slate-700 font-medium">{formatDate(event.fecha)}</p>
                  {event.fecha_fin && <p className="text-xs text-slate-500">hasta {formatDate(event.fecha_fin)}</p>}
                </div>
              </div>

              <div className="flex items-start gap-3">
                <Users className="text-blue-500 mt-1" size={18} />
                <div>
                  <p className="text-xs text-slate-500 font-semibold uppercase">Funcionario / Participantes</p>
                  <p className="text-slate-700 font-medium">{event.funcionario || 'No especificado'}</p>
                  {event.participantes && <p className="text-sm text-slate-500 mt-1">{event.participantes}</p>}
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <MapPin className="text-red-500 mt-1" size={18} />
                <div>
                  <p className="text-xs text-slate-500 font-semibold uppercase">Ubicación</p>
                  <p className="text-slate-700 font-medium">{event.lugar || 'A confirmar'}</p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <DollarSign className="text-green-600 mt-1" size={18} />
                <div>
                  <p className="text-xs text-slate-500 font-semibold uppercase">Costo Total</p>
                  <p className="text-slate-900 font-mono font-bold text-lg">
                    {formatMoney(event.costo, event.moneda)}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <hr className="border-slate-100" />

          {/* Detalles Secundarios */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
              <div className="flex items-center gap-2 mb-1 text-slate-500">
                <Building size={14} /> <span className="text-xs font-bold uppercase">Organizador</span>
              </div>
              <p className="text-sm text-slate-700">{event.organizador || '-'}</p>
            </div>

            <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
              <div className="flex items-center gap-2 mb-1 text-slate-500">
                <FileText size={14} /> <span className="text-xs font-bold uppercase">Expediente</span>
              </div>
              <p className="text-sm text-slate-700 font-mono">{event.num_expediente || 'S/D'}</p>
            </div>

            <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
              <div className="flex items-center gap-2 mb-1 text-slate-500">
                <Globe size={14} /> <span className="text-xs font-bold uppercase">Origen Dato</span>
              </div>
              <p className="text-xs text-slate-600 break-words">{event.origen_dato || 'Sistema'}</p>
            </div>
          </div>

        </div>

        {/* FOOTER */}
        <div className="bg-slate-50 px-6 py-3 border-t border-slate-200 text-right">
          <button 
            onClick={onClose}
            className="px-4 py-2 bg-white border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-100 transition-colors text-sm font-medium"
          >
            Cerrar Ficha
          </button>
        </div>
      </div>
    </div>
  );
};