import type { DocumentType } from './document';

export type FieldType = 'text' | 'number' | 'date' | 'rut' | 'currency';

export interface TemplateField {
  id: string;
  name: string;
  label: string;
  field_type: FieldType;
  pattern: string;
  pattern_flags: string;
  required: boolean;
  order: number;
  validation_rules: Record<string, unknown> | null;
  post_processing: string | null;
}

export interface Template {
  id: string;
  name: string;
  code: string;
  description: string | null;
  doc_type: DocumentType;
  is_active: boolean;
  priority: number;
  classification_keywords: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface TemplateDetail extends Template {
  fields: TemplateField[];
}

export interface TemplateListResponse {
  items: Template[];
  total: number;
}

export interface TemplateFieldCreate {
  name: string;
  label: string;
  field_type: FieldType;
  pattern: string;
  pattern_flags?: string;
  required?: boolean;
  order?: number;
  validation_rules?: Record<string, unknown>;
  post_processing?: string;
}

export interface TemplateCreate {
  name: string;
  code: string;
  description?: string;
  doc_type: DocumentType;
  is_active?: boolean;
  priority?: number;
  classification_keywords?: string[];
  fields?: TemplateFieldCreate[];
}
