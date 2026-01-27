from __future__ import annotations
from datetime import datetime
from typing import Optional, List
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
    validation_rules: Optional[dict] = None
    post_processing: Optional[str] = None


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
    validation_rules: Optional[dict] = None
    post_processing: Optional[str] = None


class TemplateCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    doc_type: DocumentType
    is_active: bool = True
    priority: int = 0
    classification_keywords: Optional[List[str]] = None
    fields: List[TemplateFieldCreate] = []


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    classification_keywords: Optional[List[str]] = None


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    description: Optional[str] = None
    doc_type: DocumentType
    is_active: bool
    priority: int
    classification_keywords: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime


class TemplateDetailResponse(TemplateResponse):
    fields: List[TemplateFieldResponse] = []


class TemplateListResponse(BaseModel):
    items: List[TemplateResponse]
    total: int
