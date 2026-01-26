from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from models.document import DocumentType, FieldType


class TemplateFieldCreate(BaseModel):
    name: str
    label: str
    field_type: FieldType = FieldType.TEXT
    pattern: str
    pattern_flags: str = "IGNORECASE"
    required: bool = False
    order: int = 0
    validation_rules: dict | None = None
    post_processing: str | None = None


class TemplateFieldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    label: str
    field_type: FieldType
    pattern: str
    pattern_flags: str
    required: bool
    order: int
    validation_rules: dict | None
    post_processing: str | None


class TemplateCreate(BaseModel):
    name: str
    code: str
    description: str | None = None
    doc_type: DocumentType
    is_active: bool = True
    priority: int = 0
    classification_keywords: list[str] | None = None
    fields: list[TemplateFieldCreate] = []


class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    priority: int | None = None
    classification_keywords: list[str] | None = None


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    description: str | None
    doc_type: DocumentType
    is_active: bool
    priority: int
    classification_keywords: list[str] | None
    created_at: datetime
    updated_at: datetime


class TemplateDetailResponse(TemplateResponse):
    fields: list[TemplateFieldResponse] = []


class TemplateListResponse(BaseModel):
    items: list[TemplateResponse]
    total: int
