// frontend_dashboard/src/components/AgendaTable.tsx
import { useEffect, useState } from 'react';
import { supabase } from '../supabaseClient';

// Definimos la forma de los datos para TypeScript
interface Evento {
  id_hash: string;
  fecha: string;
  titulo: string;
  funcionario: string;
  lugar: string;
  costo: number;
  moneda: string;
  ambito: string;
  origen_dato: string;
}

export const AgendaTable = () => {
  const [eventos, setEventos] = useState<Evento[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAgenda();
  }, []);

  const fetchAgenda = async () => {
    try {
      setLoading(true);
      // 🔥 AQUÍ ESTÁ LA CLAVE: Conectamos con la tabla nueva
      const { data, error } = await supabase
        .from('agenda_unificada')
        .select('*')
        .order('fecha', { ascending: true })
        .limit(100); // Límite inicial de seguridad

      if (error) throw error;
      setEventos(data || []);
    } catch (error) {
      console.error("Error cargando agenda:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="p-4 text-center text-gray-500">Cargando Agenda Unificada...</div>;

  return (
    <div className="w-full bg-white rounded-lg shadow-md overflow-hidden mt-6 border border-gray-200">
      <div className="bg-gray-50 px-6 py-4 border-b border-gray-200 flex justify-between items-center">
        <h2 className="text-lg font-bold text-gray-800">📊 Agenda Unificada (Sincronizada)</h2>
        <span className="text-xs font-mono bg-blue-100 text-blue-800 px-2 py-1 rounded">
          {eventos.length} Registros
        </span>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-gray-100 text-gray-600 uppercase font-semibold text-xs">
            <tr>
              <th className="px-6 py-3">Fecha</th>
              <th className="px-6 py-3">Funcionario</th>
              <th className="px-6 py-3">Evento / Título</th>
              <th className="px-6 py-3">Lugar</th>
              <th className="px-6 py-3">Costo</th>
              <th className="px-6 py-3">Ámbito</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {eventos.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-gray-400">
                  No hay datos visibles. Revisa la sincronización.
                </td>
              </tr>
            ) : (
              eventos.map((evt) => (
                <tr key={evt.id_hash} className="hover:bg-gray-50 transition-colors">
                  <td className="px-6 py-4 font-medium whitespace-nowrap text-gray-900">
                    {evt.fecha}
                  </td>
                  <td className="px-6 py-4 text-gray-700">
                    {evt.funcionario}
                  </td>
                  <td className="px-6 py-4 text-gray-600 max-w-xs truncate" title={evt.titulo}>
                    {evt.titulo}
                  </td>
                  <td className="px-6 py-4 text-gray-600">
                    {evt.lugar}
                  </td>
                  <td className="px-6 py-4 font-mono text-gray-700">
                    {evt.moneda} {evt.costo.toLocaleString()}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded text-xs font-semibold 
                      ${evt.ambito === 'Oficial' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}`}>
                      {evt.ambito}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};