import { useState } from 'react';
import { Download, FileJson, FileSpreadsheet } from 'lucide-react';
import { getExportUrl, getExtractionsExportUrl } from '../lib/api';
import type { DocumentType, DocumentStatus } from '../types/document';

export function ExportPanel() {
  const [exportType, setExportType] = useState<'documents' | 'extractions'>('documents');
  const [format, setFormat] = useState<'json' | 'csv'>('csv');
  const [docType, setDocType] = useState<DocumentType | ''>('');
  const [status, setStatus] = useState<DocumentStatus | ''>('');
  const [includeOCR, setIncludeOCR] = useState(false);
  const [onlyCorrected, setOnlyCorrected] = useState(false);

  const handleExport = () => {
    let url: string;

    if (exportType === 'documents') {
      url = getExportUrl(format, {
        status: status || undefined,
        doc_type: docType || undefined,
        include_extractions: true,
        include_ocr: includeOCR,
      });
    } else {
      url = getExtractionsExportUrl(format, {
        doc_type: docType || undefined,
        only_corrected: onlyCorrected,
      });
    }

    // Trigger download
    window.open(url, '_blank');
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Exportar Datos</h2>
        <p className="text-sm text-slate-400 mt-1">
          Descarga documentos procesados y datos extraídos
        </p>
      </div>

      <div className="bg-slate-800/50 rounded-xl p-6 space-y-6">
        {/* Export Type */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Tipo de Exportación
          </label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="exportType"
                value="documents"
                checked={exportType === 'documents'}
                onChange={(e) => setExportType(e.target.value as any)}
                className="text-blue-500"
              />
              <span>Documentos</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="exportType"
                value="extractions"
                checked={exportType === 'extractions'}
                onChange={(e) => setExportType(e.target.value as any)}
                className="text-blue-500"
              />
              <span>Extracciones</span>
            </label>
          </div>
        </div>

        {/* Format */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Formato
          </label>
          <div className="flex gap-4">
            <button
              onClick={() => setFormat('csv')}
              className={`flex items-center gap-2 px-4 py-3 rounded-lg border-2 transition-colors ${
                format === 'csv'
                  ? 'border-blue-500 bg-blue-500/10'
                  : 'border-slate-600 hover:border-slate-500'
              }`}
            >
              <FileSpreadsheet className="w-5 h-5" />
              <div className="text-left">
                <p className="font-medium">CSV</p>
                <p className="text-xs text-slate-400">Para Excel/Sheets</p>
              </div>
            </button>
            <button
              onClick={() => setFormat('json')}
              className={`flex items-center gap-2 px-4 py-3 rounded-lg border-2 transition-colors ${
                format === 'json'
                  ? 'border-blue-500 bg-blue-500/10'
                  : 'border-slate-600 hover:border-slate-500'
              }`}
            >
              <FileJson className="w-5 h-5" />
              <div className="text-left">
                <p className="font-medium">JSON</p>
                <p className="text-xs text-slate-400">Datos estructurados</p>
              </div>
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Tipo de Documento
            </label>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value as DocumentType | '')}
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
            >
              <option value="">Todos</option>
              <option value="boleta">Boleta</option>
              <option value="factura">Factura</option>
              <option value="guia_despacho">Guía de Despacho</option>
              <option value="nota_credito">Nota de Crédito</option>
              <option value="otro">Otro</option>
            </select>
          </div>

          {exportType === 'documents' && (
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Estado
              </label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as DocumentStatus | '')}
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
              >
                <option value="">Todos</option>
                <option value="done">Completados</option>
                <option value="error">Con Error</option>
                <option value="pending">Pendientes</option>
              </select>
            </div>
          )}
        </div>

        {/* Options */}
        <div className="space-y-2">
          {exportType === 'documents' && (
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={includeOCR}
                onChange={(e) => setIncludeOCR(e.target.checked)}
                className="rounded bg-slate-900 border-slate-600 text-blue-500"
              />
              <span className="text-sm">Incluir texto OCR completo</span>
            </label>
          )}

          {exportType === 'extractions' && (
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={onlyCorrected}
                onChange={(e) => setOnlyCorrected(e.target.checked)}
                className="rounded bg-slate-900 border-slate-600 text-blue-500"
              />
              <span className="text-sm">Solo campos corregidos manualmente</span>
            </label>
          )}
        </div>

        {/* Export Button */}
        <button
          onClick={handleExport}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg font-medium transition-colors"
        >
          <Download className="w-5 h-5" />
          Descargar {format.toUpperCase()}
        </button>
      </div>

      {/* Info */}
      <div className="bg-slate-800/30 rounded-lg p-4 text-sm text-slate-400">
        <p className="font-medium text-slate-300 mb-2">Información del Export:</p>
        <ul className="list-disc list-inside space-y-1">
          {exportType === 'documents' ? (
            <>
              <li>Incluye metadatos de cada documento (ID, nombre, tipo, estado, fechas)</li>
              <li>Los campos extraídos se incluyen como columnas adicionales</li>
              {format === 'csv' && (
                <li>Formato plano con una fila por documento</li>
              )}
              {format === 'json' && (
                <li>Formato anidado con extracciones agrupadas por documento</li>
              )}
            </>
          ) : (
            <>
              <li>Una fila por campo extraído</li>
              <li>Incluye valor original y valor corregido (si aplica)</li>
              <li>Útil para análisis de precisión y entrenamiento</li>
            </>
          )}
        </ul>
      </div>
    </div>
  );
}
