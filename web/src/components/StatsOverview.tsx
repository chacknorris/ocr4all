import { useQuery } from '@tanstack/react-query';
import {
  FileText,
  CheckCircle2,
  AlertCircle,
  Clock,
  TrendingUp,
  Layers,
  Edit3,
  Activity,
  Loader2
} from 'lucide-react';

interface OverviewStats {
  totals: {
    documents: number;
    pages: number;
    extractions: number;
    corrections: number;
  };
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  averages: {
    confidence: number | null;
    correction_rate: number;
  };
  recent_24h: number;
}

interface QueueStatus {
  queue: {
    pending: number;
    processing: number;
    recent_errors: number;
  };
  performance: {
    avg_processing_time_ms: number | null;
  };
}

async function getOverview(): Promise<OverviewStats> {
  const res = await fetch('/api/v1/stats/overview');
  return res.json();
}

async function getQueueStatus(): Promise<QueueStatus> {
  const res = await fetch('/api/v1/stats/queue-status');
  return res.json();
}

export function StatsOverview() {
  const { data: overview, isLoading: loadingOverview } = useQuery({
    queryKey: ['stats-overview'],
    queryFn: getOverview,
    refetchInterval: 30000, // Refresh every 30s
  });

  const { data: queue, isLoading: loadingQueue } = useQuery({
    queryKey: ['stats-queue'],
    queryFn: getQueueStatus,
    refetchInterval: 10000, // Refresh every 10s
  });

  if (loadingOverview || loadingQueue) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  const stats = [
    {
      label: 'Total Documentos',
      value: overview?.totals.documents ?? 0,
      icon: <FileText className="w-6 h-6" />,
      color: 'bg-blue-500',
    },
    {
      label: 'Páginas Procesadas',
      value: overview?.totals.pages ?? 0,
      icon: <Layers className="w-6 h-6" />,
      color: 'bg-purple-500',
    },
    {
      label: 'Campos Extraídos',
      value: overview?.totals.extractions ?? 0,
      icon: <TrendingUp className="w-6 h-6" />,
      color: 'bg-green-500',
    },
    {
      label: 'Correcciones',
      value: overview?.totals.corrections ?? 0,
      icon: <Edit3 className="w-6 h-6" />,
      color: 'bg-yellow-500',
    },
  ];

  const statusCards = [
    {
      label: 'Completados',
      value: overview?.by_status?.done ?? 0,
      icon: <CheckCircle2 className="w-5 h-5" />,
      color: 'text-green-400',
      bgColor: 'bg-green-400/10',
    },
    {
      label: 'Pendientes',
      value: queue?.queue.pending ?? 0,
      icon: <Clock className="w-5 h-5" />,
      color: 'text-yellow-400',
      bgColor: 'bg-yellow-400/10',
    },
    {
      label: 'Procesando',
      value: queue?.queue.processing ?? 0,
      icon: <Activity className="w-5 h-5" />,
      color: 'text-blue-400',
      bgColor: 'bg-blue-400/10',
    },
    {
      label: 'Errores (1h)',
      value: queue?.queue.recent_errors ?? 0,
      icon: <AlertCircle className="w-5 h-5" />,
      color: 'text-red-400',
      bgColor: 'bg-red-400/10',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Main Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="bg-slate-800/50 rounded-xl p-6"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">{stat.label}</p>
                <p className="text-3xl font-bold mt-1">
                  {stat.value.toLocaleString()}
                </p>
              </div>
              <div className={`${stat.color} p-3 rounded-lg text-white`}>
                {stat.icon}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Status & Queue */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Queue Status */}
        <div className="bg-slate-800/50 rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Estado de la Cola</h3>
          <div className="grid grid-cols-2 gap-4">
            {statusCards.map((card) => (
              <div
                key={card.label}
                className={`${card.bgColor} rounded-lg p-4`}
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className={card.color}>{card.icon}</span>
                  <span className="text-sm text-slate-300">{card.label}</span>
                </div>
                <p className={`text-2xl font-bold ${card.color}`}>
                  {card.value}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Performance */}
        <div className="bg-slate-800/50 rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Rendimiento</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Confianza Promedio OCR</span>
              <span className="text-xl font-bold">
                {overview?.averages.confidence
                  ? `${overview.averages.confidence}%`
                  : 'N/A'}
              </span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-2">
              <div
                className="bg-green-500 h-2 rounded-full"
                style={{ width: `${overview?.averages.confidence ?? 0}%` }}
              />
            </div>

            <div className="flex items-center justify-between mt-4">
              <span className="text-slate-400">Tasa de Corrección</span>
              <span className="text-xl font-bold">
                {overview?.averages.correction_rate.toFixed(1)}%
              </span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-2">
              <div
                className="bg-yellow-500 h-2 rounded-full"
                style={{ width: `${Math.min(100, overview?.averages.correction_rate ?? 0)}%` }}
              />
            </div>

            <div className="flex items-center justify-between mt-4">
              <span className="text-slate-400">Tiempo Promedio OCR</span>
              <span className="text-xl font-bold">
                {queue?.performance.avg_processing_time_ms
                  ? `${(queue.performance.avg_processing_time_ms / 1000).toFixed(1)}s`
                  : 'N/A'}
              </span>
            </div>

            <div className="flex items-center justify-between mt-4">
              <span className="text-slate-400">Procesados (24h)</span>
              <span className="text-xl font-bold text-blue-400">
                {overview?.recent_24h ?? 0}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* By Type */}
      <div className="bg-slate-800/50 rounded-xl p-6">
        <h3 className="text-lg font-semibold mb-4">Por Tipo de Documento</h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {Object.entries(overview?.by_type ?? {}).map(([type, count]) => (
            <div key={type} className="text-center">
              <p className="text-2xl font-bold">{count}</p>
              <p className="text-sm text-slate-400 capitalize">
                {type.replace('_', ' ')}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
