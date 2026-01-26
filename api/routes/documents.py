from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
    ExtractionResponse,
    ExtractionUpdate,
    OCRResultResponse,
)
from core.storage import get_storage
from models import get_db, Document, DocumentStatus, DocumentType, Extraction, OCRResult

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: DocumentStatus | None = None,
    doc_type: DocumentType | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all documents with pagination and filters."""
    query = select(Document).order_by(Document.created_at.desc())

    if status:
        query = query.where(Document.status == status)
    if doc_type:
        query = query.where(Document.doc_type == doc_type)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    documents = result.scalars().all()

    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single document by ID."""
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentResponse.model_validate(document)


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    update: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update document metadata."""
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if update.doc_type is not None:
        document.doc_type = update.doc_type
    if update.status is not None:
        document.status = update.status

    await db.commit()
    await db.refresh(document)

    return DocumentResponse.model_validate(document)


@router.delete("/{document_id}")
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a document and all associated data."""
    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from storage
    storage = get_storage()
    storage.delete(document.storage_path)

    await db.delete(document)
    await db.commit()

    return {"message": "Document deleted"}


@router.get("/{document_id}/ocr", response_model=list[OCRResultResponse])
async def get_ocr_results(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get OCR results for a document."""
    query = (
        select(OCRResult)
        .where(OCRResult.document_id == document_id)
        .order_by(OCRResult.page_number)
    )
    result = await db.execute(query)
    ocr_results = result.scalars().all()

    return [OCRResultResponse.model_validate(r) for r in ocr_results]


@router.get("/{document_id}/extractions", response_model=list[ExtractionResponse])
async def get_extractions(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get extracted metadata for a document."""
    query = (
        select(Extraction)
        .where(Extraction.document_id == document_id)
        .order_by(Extraction.field_name)
    )
    result = await db.execute(query)
    extractions = result.scalars().all()

    return [ExtractionResponse.model_validate(e) for e in extractions]


@router.patch("/{document_id}/extractions/{extraction_id}", response_model=ExtractionResponse)
async def update_extraction(
    document_id: UUID,
    extraction_id: UUID,
    update: ExtractionUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Manually correct an extracted value."""
    query = select(Extraction).where(
        Extraction.id == extraction_id,
        Extraction.document_id == document_id,
    )
    result = await db.execute(query)
    extraction = result.scalar_one_or_none()

    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")

    extraction.corrected_value = update.corrected_value
    extraction.manually_corrected = True

    await db.commit()
    await db.refresh(extraction)

    return ExtractionResponse.model_validate(extraction)


@router.get("/{document_id}/text")
async def get_full_text(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get concatenated text from all pages."""
    query = (
        select(OCRResult)
        .where(OCRResult.document_id == document_id)
        .order_by(OCRResult.page_number)
    )
    result = await db.execute(query)
    ocr_results = result.scalars().all()

    full_text = "\n\n".join(r.raw_text for r in ocr_results)

    return {"text": full_text, "pages": len(ocr_results)}


@router.post("/{document_id}/reprocess")
async def reprocess_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Re-run OCR on a document."""
    from workers.tasks import process_document_ocr

    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Clear existing results
    await db.execute(
        select(OCRResult).where(OCRResult.document_id == document_id).delete()
    )
    await db.execute(
        select(Extraction).where(Extraction.document_id == document_id).delete()
    )

    document.status = DocumentStatus.PENDING
    await db.commit()

    process_document_ocr.delay(str(document_id))

    return {"message": "Document queued for reprocessing"}


@router.post("/{document_id}/extract-llm")
async def extract_with_llm_endpoint(
    document_id: UUID,
    provider: str = Query(default="ollama", description="LLM provider: ollama or openai"),
    model: str | None = Query(default=None, description="Model name (e.g., llama3.2, gpt-4)"),
    db: AsyncSession = Depends(get_db),
):
    """
    Run LLM-based extraction on a document.

    This is useful for complex documents where regex-based extraction
    doesn't work well. Requires OCR to be completed first.
    """
    from workers.tasks import extract_with_llm_task

    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status not in [DocumentStatus.OCR_DONE, DocumentStatus.DONE]:
        raise HTTPException(
            status_code=400,
            detail=f"Document must have OCR completed. Current status: {document.status.value}",
        )

    # Queue LLM extraction
    extract_with_llm_task.delay(
        str(document_id),
        provider=provider,
        model=model,
    )

    return {
        "message": "LLM extraction queued",
        "document_id": str(document_id),
        "provider": provider,
        "model": model or ("llama3.2" if provider == "ollama" else "gpt-4"),
    }


@router.post("/{document_id}/extract-hybrid")
async def hybrid_extraction_endpoint(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Run hybrid extraction: regex first, then LLM for missing required fields.
    """
    from workers.tasks import hybrid_extraction

    query = select(Document).where(Document.id == document_id)
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status not in [DocumentStatus.OCR_DONE, DocumentStatus.DONE]:
        raise HTTPException(
            status_code=400,
            detail=f"Document must have OCR completed. Current status: {document.status.value}",
        )

    # Queue hybrid extraction
    hybrid_extraction.delay(str(document_id), use_llm_fallback=True)

    return {
        "message": "Hybrid extraction queued",
        "document_id": str(document_id),
    }
