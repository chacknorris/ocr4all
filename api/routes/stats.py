from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db, Document, DocumentStatus, DocumentType, Extraction, OCRResult, ProcessingStats

router = APIRouter(prefix="/stats", tags=["statistics"])


@router.get("/overview")
async def get_overview(
    db: AsyncSession = Depends(get_db),
):
    """Get overall system statistics."""
    # Total documents by status
    status_query = (
        select(Document.status, func.count(Document.id))
        .group_by(Document.status)
    )
    status_result = await db.execute(status_query)
    status_counts = {row[0].value: row[1] for row in status_result}

    # Total documents by type
    type_query = (
        select(Document.doc_type, func.count(Document.id))
        .group_by(Document.doc_type)
    )
    type_result = await db.execute(type_query)
    type_counts = {row[0].value: row[1] for row in type_result}

    # Total pages processed
    pages_query = select(func.sum(Document.page_count)).where(
        Document.status == DocumentStatus.DONE
    )
    pages_result = await db.execute(pages_query)
    total_pages = pages_result.scalar() or 0

    # Average confidence
    conf_query = select(func.avg(OCRResult.confidence)).where(
        OCRResult.confidence.isnot(None)
    )
    conf_result = await db.execute(conf_query)
    avg_confidence = conf_result.scalar()

    # Extraction stats
    extraction_query = select(
        func.count(Extraction.id),
        func.sum(case((Extraction.manually_corrected == True, 1), else_=0))
    )
    extraction_result = await db.execute(extraction_query)
    extraction_row = extraction_result.first()
    total_extractions = extraction_row[0] or 0
    total_corrections = extraction_row[1] or 0

    # Recent processing (last 24h)
    yesterday = datetime.utcnow() - timedelta(hours=24)
    recent_query = select(func.count(Document.id)).where(
        Document.processed_at >= yesterday
    )
    recent_result = await db.execute(recent_query)
    recent_processed = recent_result.scalar() or 0

    return {
        "totals": {
            "documents": sum(status_counts.values()),
            "pages": total_pages,
            "extractions": total_extractions,
            "corrections": total_corrections,
        },
        "by_status": status_counts,
        "by_type": type_counts,
        "averages": {
            "confidence": round(avg_confidence, 2) if avg_confidence else None,
            "correction_rate": round(total_corrections / total_extractions * 100, 2) if total_extractions > 0 else 0,
        },
        "recent_24h": recent_processed,
    }


@router.get("/timeline")
async def get_timeline(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get processing timeline data for charts."""
    start_date = datetime.utcnow() - timedelta(days=days)

    # Documents processed per day
    daily_query = (
        select(
            func.date_trunc('day', Document.created_at).label('date'),
            func.count(Document.id).label('total'),
            func.sum(case((Document.status == DocumentStatus.DONE, 1), else_=0)).label('completed'),
            func.sum(case((Document.status == DocumentStatus.ERROR, 1), else_=0)).label('failed'),
        )
        .where(Document.created_at >= start_date)
        .group_by(func.date_trunc('day', Document.created_at))
        .order_by(func.date_trunc('day', Document.created_at))
    )

    result = await db.execute(daily_query)
    timeline = [
        {
            "date": row.date.isoformat() if row.date else None,
            "total": row.total,
            "completed": row.completed or 0,
            "failed": row.failed or 0,
        }
        for row in result
    ]

    return {"timeline": timeline, "days": days}


@router.get("/by-type")
async def get_stats_by_type(
    db: AsyncSession = Depends(get_db),
):
    """Get detailed statistics grouped by document type."""
    query = (
        select(
            Document.doc_type,
            func.count(Document.id).label('count'),
            func.sum(Document.page_count).label('pages'),
            func.avg(Document.page_count).label('avg_pages'),
        )
        .where(Document.status == DocumentStatus.DONE)
        .group_by(Document.doc_type)
    )

    result = await db.execute(query)

    stats = []
    for row in result:
        # Get confidence for this type
        conf_query = (
            select(func.avg(OCRResult.confidence))
            .join(Document)
            .where(
                Document.doc_type == row.doc_type,
                OCRResult.confidence.isnot(None)
            )
        )
        conf_result = await db.execute(conf_query)
        avg_conf = conf_result.scalar()

        # Get extraction stats for this type
        ext_query = (
            select(
                func.count(Extraction.id),
                func.sum(case((Extraction.manually_corrected == True, 1), else_=0))
            )
            .join(Document)
            .where(Document.doc_type == row.doc_type)
        )
        ext_result = await db.execute(ext_query)
        ext_row = ext_result.first()

        stats.append({
            "doc_type": row.doc_type.value,
            "count": row.count,
            "pages": row.pages or 0,
            "avg_pages": round(row.avg_pages, 1) if row.avg_pages else 0,
            "avg_confidence": round(avg_conf, 2) if avg_conf else None,
            "extractions": ext_row[0] or 0,
            "corrections": ext_row[1] or 0,
        })

    return {"stats": stats}


@router.get("/extraction-accuracy")
async def get_extraction_accuracy(
    db: AsyncSession = Depends(get_db),
):
    """Get extraction accuracy statistics by field."""
    query = (
        select(
            Extraction.field_name,
            func.count(Extraction.id).label('total'),
            func.sum(case((Extraction.extracted_value.isnot(None), 1), else_=0)).label('extracted'),
            func.sum(case((Extraction.manually_corrected == True, 1), else_=0)).label('corrected'),
            func.avg(Extraction.confidence).label('avg_confidence'),
        )
        .group_by(Extraction.field_name)
        .order_by(func.count(Extraction.id).desc())
    )

    result = await db.execute(query)

    accuracy = []
    for row in result:
        extracted = row.extracted or 0
        corrected = row.corrected or 0
        total = row.total

        # Accuracy = fields that didn't need correction / total extracted
        accurate = extracted - corrected
        accuracy_rate = accurate / extracted * 100 if extracted > 0 else 0

        accuracy.append({
            "field_name": row.field_name,
            "total": total,
            "extracted": extracted,
            "corrected": corrected,
            "accuracy_rate": round(accuracy_rate, 2),
            "avg_confidence": round(row.avg_confidence, 2) if row.avg_confidence else None,
        })

    return {"accuracy": accuracy}


@router.get("/queue-status")
async def get_queue_status(
    db: AsyncSession = Depends(get_db),
):
    """Get current processing queue status."""
    # Pending documents
    pending_query = select(func.count(Document.id)).where(
        Document.status == DocumentStatus.PENDING
    )
    pending_result = await db.execute(pending_query)
    pending = pending_result.scalar() or 0

    # Processing documents
    processing_query = select(func.count(Document.id)).where(
        Document.status.in_([DocumentStatus.PROCESSING, DocumentStatus.OCR_DONE, DocumentStatus.EXTRACTING])
    )
    processing_result = await db.execute(processing_query)
    processing = processing_result.scalar() or 0

    # Recent errors (last hour)
    hour_ago = datetime.utcnow() - timedelta(hours=1)
    errors_query = select(func.count(Document.id)).where(
        Document.status == DocumentStatus.ERROR,
        Document.updated_at >= hour_ago
    )
    errors_result = await db.execute(errors_query)
    recent_errors = errors_result.scalar() or 0

    # Average processing time (last 100 documents)
    time_query = (
        select(func.avg(OCRResult.processing_time_ms))
        .where(OCRResult.processing_time_ms.isnot(None))
        .limit(100)
    )
    time_result = await db.execute(time_query)
    avg_time = time_result.scalar()

    return {
        "queue": {
            "pending": pending,
            "processing": processing,
            "recent_errors": recent_errors,
        },
        "performance": {
            "avg_processing_time_ms": int(avg_time) if avg_time else None,
        }
    }
