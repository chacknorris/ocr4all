import axios from 'axios';
import type {
  Document,
  DocumentListResponse,
  Extraction,
  OCRResult,
  UploadResponse,
  DocumentType
} from '../types/document';
import type {
  Template,
  TemplateDetail,
  TemplateListResponse,
  TemplateCreate,
  TemplateFieldCreate,
  TemplateField,
} from '../types/template';

const api = axios.create({
  baseURL: '/api/v1',
});

export async function uploadDocument(
  file: File,
  docType: DocumentType = 'otro'
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('doc_type', docType);

  const response = await api.post<UploadResponse>('/upload', formData);
  return response.data;
}

export async function uploadBatch(
  files: File[],
  docType: DocumentType = 'otro'
): Promise<UploadResponse[]> {
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));
  formData.append('doc_type', docType);

  const response = await api.post<UploadResponse[]>('/upload/batch', formData);
  return response.data;
}

export async function getDocuments(params?: {
  page?: number;
  page_size?: number;
  status?: string;
  doc_type?: string;
}): Promise<DocumentListResponse> {
  const response = await api.get<DocumentListResponse>('/documents', { params });
  return response.data;
}

export async function getDocument(id: string): Promise<Document> {
  const response = await api.get<Document>(`/documents/${id}`);
  return response.data;
}

export async function deleteDocument(id: string): Promise<void> {
  await api.delete(`/documents/${id}`);
}

export async function getOCRResults(documentId: string): Promise<OCRResult[]> {
  const response = await api.get<OCRResult[]>(`/documents/${documentId}/ocr`);
  return response.data;
}

export async function getExtractions(documentId: string): Promise<Extraction[]> {
  const response = await api.get<Extraction[]>(`/documents/${documentId}/extractions`);
  return response.data;
}

export async function updateExtraction(
  documentId: string,
  extractionId: string,
  correctedValue: string
): Promise<Extraction> {
  const response = await api.patch<Extraction>(
    `/documents/${documentId}/extractions/${extractionId}`,
    { corrected_value: correctedValue }
  );
  return response.data;
}

export async function reprocessDocument(id: string): Promise<void> {
  await api.post(`/documents/${id}/reprocess`);
}

export async function getFullText(documentId: string): Promise<{ text: string; pages: number }> {
  const response = await api.get<{ text: string; pages: number }>(
    `/documents/${documentId}/text`
  );
  return response.data;
}

export async function getHealth(): Promise<{
  status: string;
  tesseract_version: string;
  available_languages: string[];
}> {
  const response = await api.get('/health');
  return response.data;
}

// Templates
export async function getTemplates(params?: {
  doc_type?: DocumentType;
  active_only?: boolean;
}): Promise<TemplateListResponse> {
  const response = await api.get<TemplateListResponse>('/templates', { params });
  return response.data;
}

export async function getTemplate(id: string): Promise<TemplateDetail> {
  const response = await api.get<TemplateDetail>(`/templates/${id}`);
  return response.data;
}

export async function createTemplate(data: TemplateCreate): Promise<TemplateDetail> {
  const response = await api.post<TemplateDetail>('/templates', data);
  return response.data;
}

export async function updateTemplate(
  id: string,
  data: Partial<Template>
): Promise<Template> {
  const response = await api.patch<Template>(`/templates/${id}`, data);
  return response.data;
}

export async function deleteTemplate(id: string): Promise<void> {
  await api.delete(`/templates/${id}`);
}

export async function addTemplateField(
  templateId: string,
  data: TemplateFieldCreate
): Promise<TemplateField> {
  const response = await api.post<TemplateField>(`/templates/${templateId}/fields`, data);
  return response.data;
}

export async function updateTemplateField(
  templateId: string,
  fieldId: string,
  data: TemplateFieldCreate
): Promise<TemplateField> {
  const response = await api.patch<TemplateField>(
    `/templates/${templateId}/fields/${fieldId}`,
    data
  );
  return response.data;
}

export async function deleteTemplateField(
  templateId: string,
  fieldId: string
): Promise<void> {
  await api.delete(`/templates/${templateId}/fields/${fieldId}`);
}

export async function seedDefaultTemplates(): Promise<{ message: string; templates: string[] }> {
  const response = await api.post<{ message: string; templates: string[] }>('/templates/seed-defaults');
  return response.data;
}

// Export
export function getExportUrl(
  format: 'json' | 'csv',
  params?: {
    status?: string;
    doc_type?: string;
    include_extractions?: boolean;
    include_ocr?: boolean;
  }
): string {
  const searchParams = new URLSearchParams({ format });
  if (params?.status) searchParams.set('status', params.status);
  if (params?.doc_type) searchParams.set('doc_type', params.doc_type);
  if (params?.include_extractions !== undefined)
    searchParams.set('include_extractions', String(params.include_extractions));
  if (params?.include_ocr !== undefined)
    searchParams.set('include_ocr', String(params.include_ocr));

  return `/api/v1/export/documents?${searchParams.toString()}`;
}

export function getExtractionsExportUrl(
  format: 'json' | 'csv',
  params?: {
    doc_type?: string;
    only_corrected?: boolean;
  }
): string {
  const searchParams = new URLSearchParams({ format });
  if (params?.doc_type) searchParams.set('doc_type', params.doc_type);
  if (params?.only_corrected !== undefined)
    searchParams.set('only_corrected', String(params.only_corrected));

  return `/api/v1/export/extractions?${searchParams.toString()}`;
}
