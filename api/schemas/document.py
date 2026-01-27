from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from models.document import DocumentStatus, DocumentType


class DocumentCreate(BaseModel):
    doc_type: DocumentType = DocumentType.OTRO


class DocumentUpdate(BaseModel):
    doc_type: Optional[DocumentType] = None
    status: Optional[DocumentStatus] = None


class OCRResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    page_number: int
    raw_text: str
    confidence: Optional[float] = None
    processing_time_ms: Optional[int] = None
    image_path: Optional[str] = None
    created_at: datetime


class ExtractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    field_name: str
    extracted_value: Optional[str] = None
    confidence: Optional[float] = None
    manually_corrected: bool
    corrected_value: Optional[str] = None
    source_page: Optional[int] = None
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
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None


class DocumentDetailResponse(DocumentResponse):
    ocr_results: List[OCRResultResponse] = []
    extractions: List[ExtractionResponse] = []


class DocumentListResponse(BaseModel):
    items: List[DocumentResponse]
    total: int
    page: int
    page_size: int
    pages: int


class UploadResponse(BaseModel):
    id: UUID
    filename: str
    status: DocumentStatus
    message: str
