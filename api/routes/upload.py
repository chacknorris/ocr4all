from __future__ import annotations
from fastapi import APIRouter, File, Form, UploadFile, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.document import UploadResponse
from core.auth import OptionalAuth
from core.storage import get_storage
from models import get_db, Document, DocumentStatus, DocumentType
from workers.tasks import process_document_ocr

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
    "image/webp",
    "application/pdf",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: DocumentType = Form(default=DocumentType.OTRO),
    auth: OptionalAuth = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document for OCR processing.

    Accepts images (PNG, JPEG, TIFF, WebP) and PDFs.
    Optional authentication via X-API-Key header for multi-tenancy.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename required")

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Allowed: {', '.join(ALLOWED_MIME_TYPES)}",
        )

    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB",
        )

    storage = get_storage()
    storage_path = storage.save(content, file.filename, folder="originals")

    # Capture organization_id if authenticated
    org_id = auth.org_id if auth else None

    document = Document(
        organization_id=org_id,
        filename=storage_path.split("/")[-1],
        original_filename=file.filename,
        mime_type=file.content_type,
        file_size=len(content),
        doc_type=doc_type,
        status=DocumentStatus.PENDING,
        storage_path=storage_path,
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Queue OCR task
    process_document_ocr.delay(str(document.id))

    return UploadResponse(
        id=document.id,
        filename=document.original_filename,
        status=document.status,
        message="Document queued for processing",
    )


@router.post("/batch", response_model=list[UploadResponse])
async def upload_batch(
    files: list[UploadFile] = File(...),
    doc_type: DocumentType = Form(default=DocumentType.OTRO),
    auth: OptionalAuth = None,
    db: AsyncSession = Depends(get_db),
):
    """Upload multiple documents at once. Optional authentication for multi-tenancy."""
    results = []
    storage = get_storage()
    org_id = auth.org_id if auth else None

    for file in files:
        if not file.filename:
            continue

        if file.content_type not in ALLOWED_MIME_TYPES:
            results.append(
                UploadResponse(
                    id=None,
                    filename=file.filename,
                    status=DocumentStatus.ERROR,
                    message=f"Unsupported file type: {file.content_type}",
                )
            )
            continue

        content = await file.read()

        if len(content) > MAX_FILE_SIZE:
            results.append(
                UploadResponse(
                    id=None,
                    filename=file.filename,
                    status=DocumentStatus.ERROR,
                    message="File too large",
                )
            )
            continue

        storage_path = storage.save(content, file.filename, folder="originals")

        document = Document(
            organization_id=org_id,
            filename=storage_path.split("/")[-1],
            original_filename=file.filename,
            mime_type=file.content_type,
            file_size=len(content),
            doc_type=doc_type,
            status=DocumentStatus.PENDING,
            storage_path=storage_path,
        )

        db.add(document)
        await db.flush()

        process_document_ocr.delay(str(document.id))

        results.append(
            UploadResponse(
                id=document.id,
                filename=document.original_filename,
                status=document.status,
                message="Queued for processing",
            )
        )

    await db.commit()
    return results
