import csv
import io
import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import get_db, Document, DocumentStatus, DocumentType, Extraction, OCRResult

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/documents")
async def export_documents(
    format: str = Query("json", enum=["json", "csv"]),
    status: DocumentStatus | None = None,
    doc_type: DocumentType | None = None,
    include_extractions: bool = True,
    include_ocr: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    Export documents with their extracted data.

    Formats:
    - json: Full document data with nested extractions
    - csv: Flattened table with one row per document
    """
    query = select(Document).order_by(Document.created_at.desc())

    if status:
        query = query.where(Document.status == status)
    if doc_type:
        query = query.where(Document.doc_type == doc_type)

    if include_extractions:
        query = query.options(selectinload(Document.extractions))
    if include_ocr:
        query = query.options(selectinload(Document.ocr_results))

    result = await db.execute(query)
    documents = result.scalars().all()

    if format == "json":
        return _export_json(documents, include_extractions, include_ocr)
    else:
        return _export_csv(documents, include_extractions)


@router.get("/documents/{document_id}")
async def export_single_document(
    document_id: UUID,
    format: str = Query("json", enum=["json", "csv"]),
    db: AsyncSession = Depends(get_db),
):
    """Export a single document with all its data."""
    query = (
        select(Document)
        .options(
            selectinload(Document.extractions),
            selectinload(Document.ocr_results),
        )
        .where(Document.id == document_id)
    )
    result = await db.execute(query)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if format == "json":
        return _export_json([document], True, True)
    else:
        return _export_csv([document], True)


@router.get("/extractions")
async def export_extractions(
    format: str = Query("json", enum=["json", "csv"]),
    doc_type: DocumentType | None = None,
    only_corrected: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    Export extracted metadata across all documents.

    Useful for analysis and validation.
    """
    query = (
        select(Document)
        .options(selectinload(Document.extractions))
        .where(Document.status == DocumentStatus.DONE)
    )

    if doc_type:
        query = query.where(Document.doc_type == doc_type)

    result = await db.execute(query)
    documents = result.scalars().all()

    # Build extraction records
    records = []
    for doc in documents:
        for ext in doc.extractions:
            if only_corrected and not ext.manually_corrected:
                continue

            records.append({
                "document_id": str(doc.id),
                "document_filename": doc.original_filename,
                "doc_type": doc.doc_type.value,
                "field_name": ext.field_name,
                "extracted_value": ext.extracted_value,
                "corrected_value": ext.corrected_value,
                "final_value": ext.corrected_value if ext.manually_corrected else ext.extracted_value,
                "confidence": ext.confidence,
                "manually_corrected": ext.manually_corrected,
                "extracted_at": ext.created_at.isoformat(),
            })

    if format == "json":
        return StreamingResponse(
            iter([json.dumps(records, indent=2, ensure_ascii=False)]),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=extractions_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            },
        )
    else:
        return _records_to_csv(records, f"extractions_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv")


def _export_json(documents: list[Document], include_extractions: bool, include_ocr: bool):
    """Export documents to JSON format."""
    data = []

    for doc in documents:
        record = {
            "id": str(doc.id),
            "filename": doc.original_filename,
            "doc_type": doc.doc_type.value,
            "status": doc.status.value,
            "page_count": doc.page_count,
            "file_size": doc.file_size,
            "created_at": doc.created_at.isoformat(),
            "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
        }

        if include_extractions and doc.extractions:
            record["extractions"] = {}
            for ext in doc.extractions:
                record["extractions"][ext.field_name] = {
                    "value": ext.corrected_value if ext.manually_corrected else ext.extracted_value,
                    "confidence": ext.confidence,
                    "corrected": ext.manually_corrected,
                }

        if include_ocr and doc.ocr_results:
            record["ocr_text"] = "\n\n".join(
                r.raw_text for r in sorted(doc.ocr_results, key=lambda x: x.page_number)
            )
            record["ocr_confidence"] = (
                sum(r.confidence or 0 for r in doc.ocr_results) / len(doc.ocr_results)
                if doc.ocr_results else None
            )

        data.append(record)

    return StreamingResponse(
        iter([json.dumps(data, indent=2, ensure_ascii=False)]),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=documents_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        },
    )


def _export_csv(documents: list[Document], include_extractions: bool):
    """Export documents to CSV format with flattened extractions."""

    # Collect all unique field names
    all_fields = set()
    if include_extractions:
        for doc in documents:
            for ext in doc.extractions:
                all_fields.add(ext.field_name)

    all_fields = sorted(all_fields)

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    header = ["id", "filename", "doc_type", "status", "page_count", "created_at", "processed_at"]
    header.extend(all_fields)
    header.extend([f"{f}_confidence" for f in all_fields])
    writer.writerow(header)

    # Rows
    for doc in documents:
        row = [
            str(doc.id),
            doc.original_filename,
            doc.doc_type.value,
            doc.status.value,
            doc.page_count,
            doc.created_at.isoformat(),
            doc.processed_at.isoformat() if doc.processed_at else "",
        ]

        # Build extraction lookup
        ext_map = {}
        if include_extractions:
            for ext in doc.extractions:
                ext_map[ext.field_name] = ext

        # Add field values
        for field in all_fields:
            ext = ext_map.get(field)
            if ext:
                value = ext.corrected_value if ext.manually_corrected else ext.extracted_value
                row.append(value or "")
            else:
                row.append("")

        # Add confidence values
        for field in all_fields:
            ext = ext_map.get(field)
            row.append(ext.confidence if ext and ext.confidence else "")

        writer.writerow(row)

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=documents_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
        },
    )


def _records_to_csv(records: list[dict], filename: str):
    """Convert records to CSV streaming response."""
    if not records:
        return StreamingResponse(
            iter([""]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
