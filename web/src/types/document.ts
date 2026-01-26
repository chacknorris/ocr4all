export type DocumentStatus =
  | 'pending'
  | 'processing'
  | 'ocr_done'
  | 'extracting'
  | 'done'
  | 'error';

export type DocumentType =
  | 'boleta'
  | 'factura'
  | 'guia_despacho'
  | 'nota_credito'
  | 'otro';

export interface Document {
  id: string;
  filename: string;
  original_filename: string;
  mime_type: string;
  file_size: number;
  doc_type: DocumentType;
  status: DocumentStatus;
  page_count: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  processed_at: string | null;
}

export interface OCRResult {
  id: string;
  page_number: number;
  raw_text: string;
  confidence: number | null;
  processing_time_ms: number | null;
  image_path: string | null;
  created_at: string;
}

export interface Extraction {
  id: string;
  field_name: string;
  extracted_value: string | null;
  confidence: number | null;
  manually_corrected: boolean;
  corrected_value: string | null;
  source_page: number | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: Document[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface UploadResponse {
  id: string;
  filename: string;
  status: DocumentStatus;
  message: string;
}
