from __future__ import annotations
from fastapi import APIRouter

from core.ocr import get_tesseract_languages, get_tesseract_version

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "tesseract_version": get_tesseract_version(),
        "available_languages": get_tesseract_languages(),
    }


@router.get("/")
async def root():
    return {
        "name": "OCR4All API",
        "version": "1.0.0",
        "docs": "/docs",
    }
