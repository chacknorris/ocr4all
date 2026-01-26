import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.database import Base


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    OCR_DONE = "ocr_done"
    EXTRACTING = "extracting"
    DONE = "done"
    ERROR = "error"


class DocumentType(str, enum.Enum):
    BOLETA = "boleta"
    FACTURA = "factura"
    GUIA_DESPACHO = "guia_despacho"
    NOTA_CREDITO = "nota_credito"
    OTRO = "otro"


class FieldType(str, enum.Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    RUT = "rut"
    CURRENCY = "currency"


class DocumentCategory(Base):
    """Dynamic document categories/types that can be created at runtime."""
    __tablename__ = "document_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_categories.id", ondelete="SET NULL"), nullable=True
    )
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Self-referential relationship for hierarchy
    parent: Mapped["DocumentCategory | None"] = relationship(
        "DocumentCategory", remote_side="DocumentCategory.id", backref="children"
    )


class ProcessingStats(Base):
    """Daily processing statistics for monitoring."""
    __tablename__ = "processing_stats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    documents_processed: Mapped[int] = mapped_column(Integer, default=0)
    documents_failed: Mapped[int] = mapped_column(Integer, default=0)
    pages_processed: Mapped[int] = mapped_column(Integer, default=0)
    avg_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extractions_count: Mapped[int] = mapped_column(Integer, default=0)
    corrections_count: Mapped[int] = mapped_column(Integer, default=0)


class ExtractionTemplate(Base):
    """Configurable extraction template for document types."""
    __tablename__ = "extraction_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    doc_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Higher = checked first
    classification_keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    fields: Mapped[list["TemplateField"]] = relationship(
        "TemplateField", back_populates="template", cascade="all, delete-orphan"
    )


class TemplateField(Base):
    """Individual field definition within a template."""
    __tablename__ = "template_fields"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extraction_templates.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    field_type: Mapped[FieldType] = mapped_column(Enum(FieldType), default=FieldType.TEXT)
    pattern: Mapped[str] = mapped_column(Text, nullable=False)  # Regex pattern
    pattern_flags: Mapped[str] = mapped_column(String(20), default="IGNORECASE")
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    order: Mapped[int] = mapped_column(Integer, default=0)
    validation_rules: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    post_processing: Mapped[str | None] = mapped_column(String(50), nullable=True)  # e.g., "normalize_rut"

    # Relationships
    template: Mapped["ExtractionTemplate"] = relationship("ExtractionTemplate", back_populates="fields")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )  # For multi-tenancy
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType), default=DocumentType.OTRO
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.PENDING
    )
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    ocr_results: Mapped[list["OCRResult"]] = relationship(
        "OCRResult", back_populates="document", cascade="all, delete-orphan"
    )
    extractions: Mapped[list["Extraction"]] = relationship(
        "Extraction", back_populates="document", cascade="all, delete-orphan"
    )


class OCRResult(Base):
    __tablename__ = "ocr_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    word_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="ocr_results")


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    extracted_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    manually_corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    corrected_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bounding_box: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extraction_method: Mapped[str] = mapped_column(
        String(20), default="regex", nullable=False
    )  # "regex", "llm", "manual"
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="extractions")

    @property
    def final_value(self) -> str | None:
        return self.corrected_value if self.manually_corrected else self.extracted_value
