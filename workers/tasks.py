import asyncio
import io
from datetime import datetime
from uuid import UUID

from celery import shared_task
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.ocr import OCRConfig, run_ocr
from core.pdf_handler import is_pdf, pdf_to_images
from core.storage import get_storage
from core.extractor import extract_with_template, classify_document, DEFAULT_TEMPLATES
from core.llm import LLMConfig, LLMExtractor, extract_with_llm
from models.document import (
    Document,
    DocumentStatus,
    DocumentType,
    Extraction,
    ExtractionTemplate,
    OCRResult,
    TemplateField,
)


def get_sync_session():
    """Get synchronous database session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.config import get_settings

    settings = get_settings()
    # Convert async URL to sync
    sync_url = settings.database_url.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@shared_task(bind=True, max_retries=3)
def process_document_ocr(self, document_id: str):
    """Process a document through OCR pipeline."""
    db = get_sync_session()
    storage = get_storage()

    try:
        doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        doc.status = DocumentStatus.PROCESSING
        db.commit()

        # Load file content
        content = storage.load(doc.storage_path)

        # Convert to images
        if is_pdf(content):
            images = pdf_to_images(content)
            doc.page_count = len(images)
        else:
            images = [Image.open(io.BytesIO(content)).convert("RGB")]
            doc.page_count = 1

        db.commit()

        # Process each page
        config = OCRConfig()
        for page_num, image in enumerate(images, start=1):
            result = run_ocr(image, config)

            # Save processed image
            img_filename = f"{doc.id}_page_{page_num}.png"
            img_path = storage.save_image(image, img_filename, folder="processed")

            ocr_result = OCRResult(
                document_id=doc.id,
                page_number=page_num,
                raw_text=result.text,
                confidence=result.confidence,
                word_data=result.word_data,
                processing_time_ms=result.processing_time_ms,
                image_path=img_path,
            )
            db.add(ocr_result)

        doc.status = DocumentStatus.OCR_DONE
        db.commit()

        # Trigger extraction
        extract_metadata.delay(document_id)

        return {"status": "success", "pages": doc.page_count}

    except Exception as e:
        db.rollback()
        doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
        if doc:
            doc.status = DocumentStatus.ERROR
            doc.error_message = str(e)
            db.commit()
        raise self.retry(exc=e, countdown=60)

    finally:
        db.close()


@shared_task(bind=True, max_retries=2)
def extract_metadata(self, document_id: str):
    """Extract structured metadata from OCR results using templates."""
    db = get_sync_session()

    try:
        doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        doc.status = DocumentStatus.EXTRACTING
        db.commit()

        # Get all OCR text
        ocr_results = (
            db.query(OCRResult)
            .filter(OCRResult.document_id == doc.id)
            .order_by(OCRResult.page_number)
            .all()
        )

        full_text = "\n".join(r.raw_text for r in ocr_results)

        # Load templates from DB
        db_templates = (
            db.query(ExtractionTemplate)
            .options(selectinload(ExtractionTemplate.fields))
            .filter(ExtractionTemplate.is_active == True)
            .order_by(ExtractionTemplate.priority.desc())
            .all()
        )

        # Build template lookup
        if db_templates:
            templates_for_classification = [
                {
                    "code": t.code,
                    "doc_type": t.doc_type.value,
                    "classification_keywords": t.classification_keywords or [],
                    "priority": t.priority,
                }
                for t in db_templates
            ]
            template_map = {t.code: t for t in db_templates}
        else:
            # Use defaults
            templates_for_classification = [
                {
                    "code": code,
                    "doc_type": data["doc_type"],
                    "classification_keywords": data.get("classification_keywords", []),
                    "priority": 0,
                }
                for code, data in DEFAULT_TEMPLATES.items()
            ]
            template_map = None

        # Auto-classify if type is unknown
        if doc.doc_type == DocumentType.OTRO:
            classified_code = classify_document(full_text, templates_for_classification)
            if classified_code:
                # Find matching doc_type
                for t in templates_for_classification:
                    if t["code"] == classified_code:
                        try:
                            doc.doc_type = DocumentType(t["doc_type"])
                        except ValueError:
                            pass
                        break
            db.commit()

        # Get template for this document type
        template_fields = None

        if template_map:
            # Find template by doc_type
            for t in db_templates:
                if t.doc_type == doc.doc_type:
                    template_fields = [
                        {
                            "name": f.name,
                            "label": f.label,
                            "pattern": f.pattern,
                            "field_type": f.field_type.value,
                            "pattern_flags": f.pattern_flags,
                            "post_processing": f.post_processing,
                            "required": f.required,
                        }
                        for f in sorted(t.fields, key=lambda x: x.order)
                    ]
                    break
        else:
            # Use default templates
            default_key = doc.doc_type.value
            if default_key in DEFAULT_TEMPLATES:
                template_fields = DEFAULT_TEMPLATES[default_key].get("fields", [])

        if not template_fields:
            # No template found, mark as done without extractions
            doc.status = DocumentStatus.DONE
            doc.processed_at = datetime.utcnow()
            db.commit()
            return {"status": "success", "doc_type": doc.doc_type.value, "extractions": 0}

        # Extract using template
        extracted = extract_with_template(full_text, template_fields)

        # Save extractions
        for field in extracted:
            extraction = Extraction(
                document_id=doc.id,
                field_name=field.field_name,
                extracted_value=field.value,
                confidence=field.confidence,
                source_page=field.source_page or 1,
            )
            db.add(extraction)

        doc.status = DocumentStatus.DONE
        doc.processed_at = datetime.utcnow()
        db.commit()

        return {
            "status": "success",
            "doc_type": doc.doc_type.value,
            "extractions": len(extracted),
        }

    except Exception as e:
        db.rollback()
        doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
        if doc:
            doc.status = DocumentStatus.ERROR
            doc.error_message = str(e)
            db.commit()
        raise self.retry(exc=e, countdown=30)

    finally:
        db.close()


@shared_task
def reprocess_all_documents(doc_type: str | None = None):
    """Reprocess all documents with current templates. Useful after template updates."""
    db = get_sync_session()

    try:
        query = db.query(Document).filter(Document.status == DocumentStatus.DONE)

        if doc_type:
            query = query.filter(Document.doc_type == DocumentType(doc_type))

        documents = query.all()

        for doc in documents:
            # Clear existing extractions
            db.query(Extraction).filter(Extraction.document_id == doc.id).delete()
            doc.status = DocumentStatus.OCR_DONE
            db.commit()

            # Re-extract
            extract_metadata.delay(str(doc.id))

        return {"status": "success", "reprocessed": len(documents)}

    finally:
        db.close()


@shared_task(bind=True, max_retries=2)
def extract_with_llm_task(
    self,
    document_id: str,
    provider: str = "ollama",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
):
    """
    Extract metadata using LLM for complex or ambiguous documents.

    This is an alternative extraction method for when regex-based
    extraction doesn't work well.

    Args:
        document_id: Document UUID
        provider: LLM provider ("ollama", "openai")
        model: Model name (e.g., "llama3.2", "gpt-4")
        base_url: API base URL
        api_key: API key for external providers
    """
    db = get_sync_session()

    try:
        doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        # Get OCR text
        ocr_results = (
            db.query(OCRResult)
            .filter(OCRResult.document_id == doc.id)
            .order_by(OCRResult.page_number)
            .all()
        )

        full_text = "\n".join(r.raw_text for r in ocr_results)

        if not full_text.strip():
            return {"status": "error", "message": "No OCR text available"}

        # Configure LLM
        config = LLMConfig(
            provider=provider,
            model=model or ("llama3.2" if provider == "ollama" else "gpt-4"),
            base_url=base_url or (
                "http://localhost:11434" if provider == "ollama"
                else "https://api.openai.com"
            ),
            api_key=api_key,
        )

        # Run extraction in async context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            extracted = loop.run_until_complete(
                extract_with_llm(full_text, doc.doc_type.value, config)
            )
        finally:
            loop.close()

        if not extracted:
            return {"status": "warning", "message": "No fields extracted by LLM"}

        # Clear existing LLM extractions (keep regex ones)
        db.query(Extraction).filter(
            Extraction.document_id == doc.id,
            Extraction.extraction_method == "llm",
        ).delete()

        # Save new extractions
        extraction_count = 0
        for field_name, value in extracted.items():
            if value is not None:
                extraction = Extraction(
                    document_id=doc.id,
                    field_name=field_name,
                    extracted_value=str(value) if not isinstance(value, str) else value,
                    confidence=0.85,  # LLM default confidence
                    source_page=1,
                    extraction_method="llm",
                )
                db.add(extraction)
                extraction_count += 1

        db.commit()

        return {
            "status": "success",
            "doc_type": doc.doc_type.value,
            "extractions": extraction_count,
            "method": "llm",
            "provider": provider,
        }

    except Exception as e:
        db.rollback()
        raise self.retry(exc=e, countdown=30)

    finally:
        db.close()


@shared_task(bind=True)
def hybrid_extraction(self, document_id: str, use_llm_fallback: bool = True):
    """
    Hybrid extraction: use regex first, then LLM for missing fields.

    Args:
        document_id: Document UUID
        use_llm_fallback: Whether to use LLM for fields that regex couldn't extract
    """
    db = get_sync_session()

    try:
        doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        # First, run standard extraction
        extract_result = extract_metadata(document_id)

        if not use_llm_fallback:
            return extract_result

        # Check for missing required fields
        existing_extractions = (
            db.query(Extraction)
            .filter(Extraction.document_id == doc.id)
            .all()
        )

        extracted_fields = {e.field_name for e in existing_extractions}

        # Get template to find required fields
        db_template = (
            db.query(ExtractionTemplate)
            .options(selectinload(ExtractionTemplate.fields))
            .filter(
                ExtractionTemplate.doc_type == doc.doc_type,
                ExtractionTemplate.is_active == True,
            )
            .first()
        )

        if db_template:
            required_fields = {
                f.name for f in db_template.fields if f.required
            }
            missing_fields = required_fields - extracted_fields

            if missing_fields:
                # Trigger LLM extraction for missing fields
                extract_with_llm_task.delay(document_id)
                return {
                    **extract_result,
                    "llm_fallback": True,
                    "missing_fields": list(missing_fields),
                }

        return extract_result

    finally:
        db.close()
