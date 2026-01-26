import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  FileText,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Eye,
  Trash2,
  RotateCcw
} from 'lucide-react';
import { getDocuments, deleteDocument, reprocessDocument } from '../lib/api';
import type { Document, DocumentStatus } from '../types/document';

interface DocumentListProps {
  onSelectDocument?: (document: Document) => void;
}

const STATUS_CONFIG: Record<DocumentStatus, { icon: React.ReactNode; label: string; color: string }> = {
  pending: {
    icon: <Clock className="w-4 h-4" />,
    label: 'Pendiente',
    color: 'text-yellow-400 bg-yellow-400/10'
  },
  processing: {
    icon: <Loader2 className="w-4 h-4 animate-spin" />,
    label: 'Procesando',
    color: 'text-blue-400 bg-blue-400/10'
  },
  ocr_done: {
    icon: <Loader2 className="w-4 h-4 animate-spin" />,
    label: 'OCR Completo',
    color: 'text-blue-400 bg-blue-400/10'
  },
  extracting: {
    icon: <Loader2 className="w-4 h-4 animate-spin" />,
    label: 'Extrayendo',
    color: 'text-purple-400 bg-purple-400/10'
  },
  done: {
    icon: <CheckCircle2 className="w-4 h-4" />,
    label: 'Completado',
    color: 'text-green-400 bg-green-400/10'
  },
  error: {
    icon: <AlertCircle className="w-4 h-4" />,
    label: 'Error',
    color: 'text-red-400 bg-red-400/10'
  },
};

const DOC_TYPE_LABELS: Record<string, string> = {
  boleta: 'Boleta',
  factura: 'Factura',
  guia_despacho: 'Guía Despacho',
  nota_credito: 'Nota Crédito',
  otro: 'Otro',
};

export function DocumentList({ onSelectDocument }: DocumentListProps) {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['documents', page, statusFilter, typeFilter],
    queryFn: () => getDocuments({
      page,
      page_size: 10,
      status: statusFilter || undefined,
      doc_type: typeFilter || undefined,
    }),
    refetchInterval: 5000, // Auto-refresh every 5s
  });

  const handleDelete = async (e: React.MouseEvent, doc: Document) => {
    e.stopPropagation();
    if (confirm(`¿Eliminar "${doc.original_filename}"?`)) {
      await deleteDocument(doc.id);
      refetch();
    }
  };

  const handleReprocess = async (e: React.MouseEvent, doc: Document) => {
    e.stopPropagation();
    await reprocessDocument(doc.id);
    refetch();
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString('es-CL', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex gap-4">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
        >
          <option value="">Todos los estados</option>
          <option value="pending">Pendiente</option>
          <option value="processing">Procesando</option>
          <option value="done">Completado</option>
          <option value="error">Error</option>
        </select>

        <select
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
        >
          <option value="">Todos los tipos</option>
          <option value="boleta">Boleta</option>
          <option value="factura">Factura</option>
          <option value="guia_despacho">Guía Despacho</option>
          <option value="nota_credito">Nota Crédito</option>
          <option value="otro">Otro</option>
        </select>

        <div className="ml-auto text-sm text-slate-400">
          {data?.total ?? 0} documentos
        </div>
      </div>

      {/* Document Table */}
      <div className="bg-slate-800/50 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead className="bg-slate-800">
            <tr className="text-left text-sm text-slate-400">
              <th className="px-4 py-3 font-medium">Documento</th>
              <th className="px-4 py-3 font-medium">Tipo</th>
              <th className="px-4 py-3 font-medium">Estado</th>
              <th className="px-4 py-3 font-medium">Páginas</th>
              <th className="px-4 py-3 font-medium">Fecha</th>
              <th className="px-4 py-3 font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700">
            {data?.items.map((doc) => {
              const status = STATUS_CONFIG[doc.status];
              return (
                <tr
                  key={doc.id}
                  onClick={() => onSelectDocument?.(doc)}
                  className="hover:bg-slate-700/50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <FileText className="w-5 h-5 text-slate-400 shrink-0" />
                      <div className="min-w-0">
                        <p className="font-medium truncate max-w-xs">
                          {doc.original_filename}
                        </p>
                        <p className="text-xs text-slate-500">
                          {formatFileSize(doc.file_size)} · {doc.mime_type.split('/')[1].toUpperCase()}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm text-slate-300">
                      {DOC_TYPE_LABELS[doc.doc_type]}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${status.color}`}>
                      {status.icon}
                      {status.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-300">
                    {doc.page_count}
                  </td>
                  <td className="px-4 py-3 text-sm text-slate-400">
                    {formatDate(doc.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); onSelectDocument?.(doc); }}
                        className="p-1.5 hover:bg-slate-600 rounded-lg transition-colors"
                        title="Ver detalles"
                      >
                        <Eye className="w-4 h-4 text-slate-400" />
                      </button>
                      <button
                        onClick={(e) => handleReprocess(e, doc)}
                        className="p-1.5 hover:bg-slate-600 rounded-lg transition-colors"
                        title="Reprocesar"
                      >
                        <RotateCcw className="w-4 h-4 text-slate-400" />
                      </button>
                      <button
                        onClick={(e) => handleDelete(e, doc)}
                        className="p-1.5 hover:bg-red-900/50 rounded-lg transition-colors"
                        title="Eliminar"
                      >
                        <Trash2 className="w-4 h-4 text-red-400" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {data?.items.length === 0 && (
          <div className="text-center py-12 text-slate-400">
            No hay documentos que mostrar
          </div>
        )}
      </div>

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-400">
            Página {page} de {data.pages}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <button
              onClick={() => setPage(p => Math.min(data.pages, p + 1))}
              disabled={page === data.pages}
              className="p-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
