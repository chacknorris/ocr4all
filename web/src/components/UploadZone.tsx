import { useCallback, useState } from 'react';
import { Upload, FileText, X, Loader2 } from 'lucide-react';
import { uploadBatch } from '../lib/api';
import type { DocumentType, UploadResponse } from '../types/document';

interface UploadZoneProps {
  onUploadComplete?: (results: UploadResponse[]) => void;
}

export function UploadZone({ onUploadComplete }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [docType, setDocType] = useState<DocumentType>('otro');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResults, setUploadResults] = useState<UploadResponse[]>([]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files).filter(
      file => file.type.startsWith('image/') || file.type === 'application/pdf'
    );
    setFiles(prev => [...prev, ...droppedFiles]);
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files);
      setFiles(prev => [...prev, ...selectedFiles]);
    }
  }, []);

  const removeFile = useCallback((index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  }, []);

  const handleUpload = async () => {
    if (files.length === 0) return;

    setIsUploading(true);
    try {
      const results = await uploadBatch(files, docType);
      setUploadResults(results);
      setFiles([]);
      onUploadComplete?.(results);
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setIsUploading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer
          ${isDragging
            ? 'border-blue-500 bg-blue-500/10'
            : 'border-slate-600 hover:border-slate-500 bg-slate-800/50'
          }
        `}
      >
        <input
          type="file"
          id="file-upload"
          className="hidden"
          multiple
          accept="image/*,application/pdf"
          onChange={handleFileSelect}
        />
        <label htmlFor="file-upload" className="cursor-pointer">
          <Upload className="w-12 h-12 mx-auto mb-4 text-slate-400" />
          <p className="text-lg font-medium text-slate-200">
            Arrastra archivos aquí o haz clic para seleccionar
          </p>
          <p className="text-sm text-slate-400 mt-2">
            Soporta imágenes (PNG, JPEG, TIFF) y PDF
          </p>
        </label>
      </div>

      {/* Document Type Selector */}
      {files.length > 0 && (
        <div className="flex items-center gap-4">
          <label className="text-sm text-slate-400">Tipo de documento:</label>
          <select
            value={docType}
            onChange={(e) => setDocType(e.target.value as DocumentType)}
            className="bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
          >
            <option value="otro">Auto-detectar</option>
            <option value="boleta">Boleta</option>
            <option value="factura">Factura</option>
            <option value="guia_despacho">Guía de Despacho</option>
            <option value="nota_credito">Nota de Crédito</option>
          </select>
        </div>
      )}

      {/* File List */}
      {files.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-medium text-slate-300">
            Archivos seleccionados ({files.length})
          </h3>
          <div className="max-h-48 overflow-y-auto space-y-2">
            {files.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                className="flex items-center justify-between bg-slate-800 rounded-lg px-4 py-2"
              >
                <div className="flex items-center gap-3">
                  <FileText className="w-5 h-5 text-slate-400" />
                  <div>
                    <p className="text-sm font-medium truncate max-w-xs">{file.name}</p>
                    <p className="text-xs text-slate-500">{formatFileSize(file.size)}</p>
                  </div>
                </div>
                <button
                  onClick={() => removeFile(index)}
                  className="p-1 hover:bg-slate-700 rounded"
                >
                  <X className="w-4 h-4 text-slate-400" />
                </button>
              </div>
            ))}
          </div>

          <button
            onClick={handleUpload}
            disabled={isUploading}
            className="w-full mt-4 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white font-medium py-3 rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            {isUploading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Subiendo...
              </>
            ) : (
              <>
                <Upload className="w-5 h-5" />
                Subir {files.length} archivo{files.length > 1 ? 's' : ''}
              </>
            )}
          </button>
        </div>
      )}

      {/* Upload Results */}
      {uploadResults.length > 0 && (
        <div className="bg-green-900/30 border border-green-700 rounded-lg p-4">
          <h3 className="text-sm font-medium text-green-400 mb-2">
            Archivos subidos exitosamente
          </h3>
          <ul className="text-sm text-green-300 space-y-1">
            {uploadResults.map((result) => (
              <li key={result.id}>
                {result.filename} - {result.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
