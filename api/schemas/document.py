from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from models.document import DocumentStatus, DocumentType


class DocumentCreate(BaseModel):
    doc_type: DocumentType = DocumentType.OTRO


class DocumentUpdate(BaseModel):
    doc_type: DocumentType | None = None
    status: DocumentStatus | None = None


class OCRResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    page_number: int
    raw_text: str
    confidence: float | None
    processing_time_ms: int | None
    image_path: str | None
    created_at: datetime


class ExtractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    field_name: str
    extracted_value: str | None
    confidence: float | None
    manually_corrected: bool
    corrected_value: str | None
    source_page: int | None
    extraction_method: str = "regex"
    created_at: datetime
    updated_at: datetime


class ExtractionUpdate(BaseModel):
    corrected_value: str


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    original_filename: str
    mime_type: str
    file_size: int
    doc_type: DocumentType
    status: DocumentStatus
    page_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None


class DocumentDetailResponse(DocumentResponse):
    ocr_results: list[OCRResultResponse] = []
    extractions: list[ExtractionResponse] = []


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int
    pages: int


class UploadResponse(BaseModel):
    id: UUID
    filename: str
    status: DocumentStatus
    message: str
