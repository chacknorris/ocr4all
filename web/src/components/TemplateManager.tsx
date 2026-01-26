import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus,
  Edit2,
  Trash2,
  ChevronDown,
  ChevronUp,
  Loader2,
  Check,
  X,
  Copy,
  Wand2
} from 'lucide-react';
import {
  getTemplates,
  getTemplate,
  createTemplate,
  deleteTemplate,
  addTemplateField,
  deleteTemplateField,
  seedDefaultTemplates,
} from '../lib/api';
import type { Template, TemplateDetail, TemplateFieldCreate } from '../types/template';
import type { DocumentType } from '../types/document';

const DOC_TYPE_OPTIONS: { value: DocumentType; label: string }[] = [
  { value: 'boleta', label: 'Boleta' },
  { value: 'factura', label: 'Factura' },
  { value: 'guia_despacho', label: 'Guía de Despacho' },
  { value: 'nota_credito', label: 'Nota de Crédito' },
  { value: 'otro', label: 'Otro' },
];

const FIELD_TYPE_OPTIONS = [
  { value: 'text', label: 'Texto' },
  { value: 'number', label: 'Número' },
  { value: 'date', label: 'Fecha' },
  { value: 'rut', label: 'RUT' },
  { value: 'currency', label: 'Moneda' },
];

const POST_PROCESSORS = [
  { value: '', label: 'Ninguno' },
  { value: 'normalize_rut', label: 'Normalizar RUT' },
  { value: 'normalize_currency', label: 'Normalizar Moneda' },
  { value: 'normalize_date', label: 'Normalizar Fecha' },
];

export function TemplateManager() {
  const [expandedTemplateId, setExpandedTemplateId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isAddingField, setIsAddingField] = useState(false);

  const queryClient = useQueryClient();

  const { data: templates, isLoading } = useQuery({
    queryKey: ['templates'],
    queryFn: () => getTemplates({ active_only: false }),
  });

  const { data: expandedTemplate } = useQuery({
    queryKey: ['template', expandedTemplateId],
    queryFn: () => getTemplate(expandedTemplateId!),
    enabled: !!expandedTemplateId,
  });

  const seedMutation = useMutation({
    mutationFn: seedDefaultTemplates,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      setExpandedTemplateId(null);
    },
  });

  const deleteFieldMutation = useMutation({
    mutationFn: ({ templateId, fieldId }: { templateId: string; fieldId: string }) =>
      deleteTemplateField(templateId, fieldId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['template', expandedTemplateId] });
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Templates de Extracción</h2>
          <p className="text-sm text-slate-400 mt-1">
            Define patrones de extracción para cada tipo de documento
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => seedMutation.mutate()}
            disabled={seedMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg transition-colors"
          >
            <Wand2 className="w-4 h-4" />
            Cargar Defaults
          </button>
          <button
            onClick={() => setIsCreating(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            Nuevo Template
          </button>
        </div>
      </div>

      {/* Template List */}
      <div className="space-y-3">
        {templates?.items.map((template) => (
          <div
            key={template.id}
            className="bg-slate-800/50 rounded-xl overflow-hidden"
          >
            {/* Template Header */}
            <button
              onClick={() =>
                setExpandedTemplateId(
                  expandedTemplateId === template.id ? null : template.id
                )
              }
              className="w-full flex items-center justify-between px-6 py-4 hover:bg-slate-700/50 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div>
                  <h3 className="font-medium text-left">{template.name}</h3>
                  <p className="text-sm text-slate-400">
                    {template.code} · {template.doc_type}
                  </p>
                </div>
                <span
                  className={`px-2 py-1 rounded text-xs font-medium ${
                    template.is_active
                      ? 'bg-green-900/50 text-green-400'
                      : 'bg-slate-700 text-slate-400'
                  }`}
                >
                  {template.is_active ? 'Activo' : 'Inactivo'}
                </span>
              </div>
              {expandedTemplateId === template.id ? (
                <ChevronUp className="w-5 h-5 text-slate-400" />
              ) : (
                <ChevronDown className="w-5 h-5 text-slate-400" />
              )}
            </button>

            {/* Expanded Content */}
            {expandedTemplateId === template.id && expandedTemplate && (
              <div className="px-6 pb-6 border-t border-slate-700">
                <div className="mt-4 space-y-4">
                  {/* Keywords */}
                  {expandedTemplate.classification_keywords &&
                    expandedTemplate.classification_keywords.length > 0 && (
                      <div>
                        <h4 className="text-sm font-medium text-slate-300 mb-2">
                          Keywords de Clasificación
                        </h4>
                        <div className="flex flex-wrap gap-2">
                          {expandedTemplate.classification_keywords.map((kw, i) => (
                            <span
                              key={i}
                              className="px-2 py-1 bg-slate-700 rounded text-sm"
                            >
                              {kw}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                  {/* Fields */}
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-sm font-medium text-slate-300">
                        Campos ({expandedTemplate.fields.length})
                      </h4>
                      <button
                        onClick={() => setIsAddingField(true)}
                        className="text-sm text-blue-400 hover:text-blue-300"
                      >
                        + Agregar Campo
                      </button>
                    </div>

                    {expandedTemplate.fields.length === 0 ? (
                      <p className="text-sm text-slate-500 italic">
                        Sin campos definidos
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {expandedTemplate.fields
                          .sort((a, b) => a.order - b.order)
                          .map((field) => (
                            <div
                              key={field.id}
                              className="flex items-start justify-between bg-slate-900/50 rounded-lg p-3"
                            >
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="font-medium">{field.label}</span>
                                  <span className="text-xs text-slate-500">
                                    ({field.name})
                                  </span>
                                  {field.required && (
                                    <span className="text-xs text-red-400">*</span>
                                  )}
                                </div>
                                <div className="flex items-center gap-3 mt-1 text-xs text-slate-400">
                                  <span className="bg-slate-800 px-2 py-0.5 rounded">
                                    {field.field_type}
                                  </span>
                                  {field.post_processing && (
                                    <span className="bg-purple-900/50 text-purple-300 px-2 py-0.5 rounded">
                                      {field.post_processing}
                                    </span>
                                  )}
                                </div>
                                <code className="block mt-2 text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded overflow-x-auto">
                                  {field.pattern}
                                </code>
                              </div>
                              <button
                                onClick={() =>
                                  deleteFieldMutation.mutate({
                                    templateId: template.id,
                                    fieldId: field.id,
                                  })
                                }
                                className="p-1 hover:bg-red-900/50 rounded"
                              >
                                <Trash2 className="w-4 h-4 text-red-400" />
                              </button>
                            </div>
                          ))}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex justify-end gap-2 pt-4 border-t border-slate-700">
                    <button
                      onClick={() => {
                        if (confirm('¿Eliminar este template?')) {
                          deleteMutation.mutate(template.id);
                        }
                      }}
                      className="px-4 py-2 text-red-400 hover:bg-red-900/30 rounded-lg transition-colors"
                    >
                      Eliminar Template
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}

        {templates?.items.length === 0 && (
          <div className="text-center py-12 text-slate-400">
            <p>No hay templates configurados.</p>
            <p className="text-sm mt-2">
              Haz clic en "Cargar Defaults" para crear los templates predeterminados.
            </p>
          </div>
        )}
      </div>

      {/* Create Template Modal */}
      {isCreating && (
        <CreateTemplateModal
          onClose={() => setIsCreating(false)}
          onCreated={() => {
            setIsCreating(false);
            queryClient.invalidateQueries({ queryKey: ['templates'] });
          }}
        />
      )}

      {/* Add Field Modal */}
      {isAddingField && expandedTemplateId && (
        <AddFieldModal
          templateId={expandedTemplateId}
          onClose={() => setIsAddingField(false)}
          onAdded={() => {
            setIsAddingField(false);
            queryClient.invalidateQueries({ queryKey: ['template', expandedTemplateId] });
          }}
        />
      )}
    </div>
  );
}

function CreateTemplateModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [formData, setFormData] = useState({
    name: '',
    code: '',
    doc_type: 'otro' as DocumentType,
    keywords: '',
  });

  const mutation = useMutation({
    mutationFn: createTemplate,
    onSuccess: onCreated,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate({
      name: formData.name,
      code: formData.code,
      doc_type: formData.doc_type,
      classification_keywords: formData.keywords
        .split(',')
        .map((k) => k.trim())
        .filter(Boolean),
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-xl w-full max-w-md p-6">
        <h3 className="text-lg font-semibold mb-4">Nuevo Template</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">Nombre</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">Código</label>
            <input
              type="text"
              value={formData.code}
              onChange={(e) =>
                setFormData({ ...formData, code: e.target.value.toLowerCase().replace(/\s/g, '_') })
              }
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">Tipo de Documento</label>
            <select
              value={formData.doc_type}
              onChange={(e) => setFormData({ ...formData, doc_type: e.target.value as DocumentType })}
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
            >
              {DOC_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">
              Keywords de Clasificación (separados por coma)
            </label>
            <input
              type="text"
              value={formData.keywords}
              onChange={(e) => setFormData({ ...formData, keywords: e.target.value })}
              placeholder="FACTURA ELECTRÓNICA, FACTURA AFECTA"
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="flex justify-end gap-2 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-slate-400 hover:bg-slate-700 rounded-lg"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg"
            >
              {mutation.isPending ? 'Creando...' : 'Crear'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function AddFieldModal({
  templateId,
  onClose,
  onAdded,
}: {
  templateId: string;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [formData, setFormData] = useState<TemplateFieldCreate>({
    name: '',
    label: '',
    field_type: 'text',
    pattern: '',
    pattern_flags: 'IGNORECASE',
    required: false,
    post_processing: '',
  });

  const mutation = useMutation({
    mutationFn: (data: TemplateFieldCreate) => addTemplateField(templateId, data),
    onSuccess: onAdded,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate({
      ...formData,
      post_processing: formData.post_processing || undefined,
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-xl w-full max-w-lg p-6">
        <h3 className="text-lg font-semibold mb-4">Agregar Campo</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">Nombre (código)</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value.toLowerCase().replace(/\s/g, '_') })
                }
                placeholder="rut_emisor"
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Etiqueta</label>
              <input
                type="text"
                value={formData.label}
                onChange={(e) => setFormData({ ...formData, label: e.target.value })}
                placeholder="RUT Emisor"
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">Tipo</label>
              <select
                value={formData.field_type}
                onChange={(e) => setFormData({ ...formData, field_type: e.target.value as any })}
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
              >
                {FIELD_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Post-procesador</label>
              <select
                value={formData.post_processing || ''}
                onChange={(e) => setFormData({ ...formData, post_processing: e.target.value })}
                className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
              >
                {POST_PROCESSORS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm text-slate-400 mb-1">Patrón Regex</label>
            <textarea
              value={formData.pattern}
              onChange={(e) => setFormData({ ...formData, pattern: e.target.value })}
              placeholder="RUT[:\s]*(\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK])"
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500 font-mono text-sm"
              rows={2}
              required
            />
            <p className="text-xs text-slate-500 mt-1">
              Usa grupos de captura () para extraer el valor
            </p>
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="required"
              checked={formData.required}
              onChange={(e) => setFormData({ ...formData, required: e.target.checked })}
              className="rounded bg-slate-900 border-slate-600"
            />
            <label htmlFor="required" className="text-sm text-slate-300">
              Campo requerido
            </label>
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-slate-400 hover:bg-slate-700 rounded-lg"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg"
            >
              {mutation.isPending ? 'Agregando...' : 'Agregar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
