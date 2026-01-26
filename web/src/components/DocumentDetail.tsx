import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  X,
  FileText,
  Check,
  Edit2,
  Loader2,
  ChevronDown,
  ChevronUp,
  Copy,
  CheckCircle2
} from 'lucide-react';
import { getOCRResults, getExtractions, updateExtraction } from '../lib/api';
import type { Document, Extraction } from '../types/document';

interface DocumentDetailProps {
  document: Document;
  onClose: () => void;
}

const FIELD_LABELS: Record<string, string> = {
  rut_emisor: 'RUT Emisor',
  rut_receptor: 'RUT Receptor',
  numero_boleta: 'N° Boleta',
  numero_factura: 'N° Factura',
  numero_guia: 'N° Guía',
  fecha: 'Fecha',
  fecha_emision: 'Fecha Emisión',
  neto: 'Neto',
  iva: 'IVA',
  total: 'Total',
};

export function DocumentDetail({ document, onClose }: DocumentDetailProps) {
  const [activeTab, setActiveTab] = useState<'extractions' | 'ocr'>('extractions');
  const [expandedPages, setExpandedPages] = useState<Set<number>>(new Set([1]));
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const queryClient = useQueryClient();

  const { data: ocrResults, isLoading: loadingOCR } = useQuery({
    queryKey: ['ocr', document.id],
    queryFn: () => getOCRResults(document.id),
    enabled: document.status === 'done' || document.status === 'ocr_done',
  });

  const { data: extractions, isLoading: loadingExtractions } = useQuery({
    queryKey: ['extractions', document.id],
    queryFn: () => getExtractions(document.id),
    enabled: document.status === 'done',
  });

  const updateMutation = useMutation({
    mutationFn: ({ extractionId, value }: { extractionId: string; value: string }) =>
      updateExtraction(document.id, extractionId, value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['extractions', document.id] });
      setEditingField(null);
    },
  });

  const handleEdit = (extraction: Extraction) => {
    setEditingField(extraction.id);
    setEditValue(extraction.corrected_value || extraction.extracted_value || '');
  };

  const handleSave = (extractionId: string) => {
    updateMutation.mutate({ extractionId, value: editValue });
  };

  const handleCopy = async (text: string, fieldId: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedField(fieldId);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const togglePage = (pageNum: number) => {
    setExpandedPages(prev => {
      const next = new Set(prev);
      if (next.has(pageNum)) {
        next.delete(pageNum);
      } else {
        next.add(pageNum);
      }
      return next;
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
          <div className="flex items-center gap-3">
            <FileText className="w-6 h-6 text-blue-400" />
            <div>
              <h2 className="font-semibold text-lg">{document.original_filename}</h2>
              <p className="text-sm text-slate-400">
                {document.page_count} página{document.page_count > 1 ? 's' : ''} ·{' '}
                {document.doc_type.replace('_', ' ')}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-700">
          <button
            onClick={() => setActiveTab('extractions')}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'extractions'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Datos Extraídos
          </button>
          <button
            onClick={() => setActiveTab('ocr')}
            className={`px-6 py-3 text-sm font-medium transition-colors ${
              activeTab === 'ocr'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Texto OCR
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'extractions' && (
            <div className="space-y-4">
              {loadingExtractions ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                </div>
              ) : extractions && extractions.length > 0 ? (
                <div className="grid gap-3">
                  {extractions.map((ext) => (
                    <div
                      key={ext.id}
                      className="flex items-center gap-4 bg-slate-700/50 rounded-lg p-4"
                    >
                      <div className="flex-1 min-w-0">
                        <label className="text-xs text-slate-400 uppercase tracking-wide">
                          {FIELD_LABELS[ext.field_name] || ext.field_name}
                        </label>
                        {editingField === ext.id ? (
                          <div className="flex items-center gap-2 mt-1">
                            <input
                              type="text"
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              className="flex-1 bg-slate-800 border border-slate-600 rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-500"
                              autoFocus
                            />
                            <button
                              onClick={() => handleSave(ext.id)}
                              disabled={updateMutation.isPending}
                              className="p-1.5 bg-green-600 hover:bg-green-700 rounded"
                            >
                              <Check className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => setEditingField(null)}
                              className="p-1.5 bg-slate-600 hover:bg-slate-500 rounded"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        ) : (
                          <p className={`text-lg font-medium ${
                            ext.extracted_value ? 'text-slate-100' : 'text-slate-500 italic'
                          }`}>
                            {ext.corrected_value || ext.extracted_value || 'No detectado'}
                            {ext.manually_corrected && (
                              <span className="ml-2 text-xs text-yellow-400">(corregido)</span>
                            )}
                          </p>
                        )}
                      </div>
                      {ext.confidence !== null && (
                        <div className={`text-sm px-2 py-1 rounded ${
                          ext.confidence >= 0.8 ? 'bg-green-900/50 text-green-400' :
                          ext.confidence >= 0.5 ? 'bg-yellow-900/50 text-yellow-400' :
                          'bg-red-900/50 text-red-400'
                        }`}>
                          {Math.round(ext.confidence * 100)}%
                        </div>
                      )}
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleCopy(ext.corrected_value || ext.extracted_value || '', ext.id)}
                          className="p-1.5 hover:bg-slate-600 rounded transition-colors"
                          title="Copiar"
                        >
                          {copiedField === ext.id ? (
                            <CheckCircle2 className="w-4 h-4 text-green-400" />
                          ) : (
                            <Copy className="w-4 h-4 text-slate-400" />
                          )}
                        </button>
                        <button
                          onClick={() => handleEdit(ext)}
                          className="p-1.5 hover:bg-slate-600 rounded transition-colors"
                          title="Editar"
                        >
                          <Edit2 className="w-4 h-4 text-slate-400" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-slate-400">
                  {document.status === 'done'
                    ? 'No se encontraron campos para extraer'
                    : 'El documento aún no ha sido procesado'}
                </div>
              )}
            </div>
          )}

          {activeTab === 'ocr' && (
            <div className="space-y-4">
              {loadingOCR ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                </div>
              ) : ocrResults && ocrResults.length > 0 ? (
                ocrResults.map((result) => (
                  <div
                    key={result.id}
                    className="bg-slate-700/50 rounded-lg overflow-hidden"
                  >
                    <button
                      onClick={() => togglePage(result.page_number)}
                      className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-700/50 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-medium">
                          Página {result.page_number}
                        </span>
                        {result.confidence !== null && (
                          <span className="text-xs text-slate-400">
                            Confianza: {result.confidence}%
                          </span>
                        )}
                        {result.processing_time_ms && (
                          <span className="text-xs text-slate-500">
                            ({result.processing_time_ms}ms)
                          </span>
                        )}
                      </div>
                      {expandedPages.has(result.page_number) ? (
                        <ChevronUp className="w-5 h-5 text-slate-400" />
                      ) : (
                        <ChevronDown className="w-5 h-5 text-slate-400" />
                      )}
                    </button>
                    {expandedPages.has(result.page_number) && (
                      <div className="px-4 pb-4">
                        <pre className="bg-slate-900 rounded-lg p-4 text-sm text-slate-300 whitespace-pre-wrap font-mono overflow-x-auto">
                          {result.raw_text || 'No se detectó texto'}
                        </pre>
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-slate-400">
                  {document.status === 'done' || document.status === 'ocr_done'
                    ? 'No hay resultados de OCR'
                    : 'El documento aún no ha sido procesado'}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
