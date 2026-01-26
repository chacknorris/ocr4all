import io
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image


def pdf_to_images(
    pdf_path: str | Path | bytes,
    dpi: int = 300,
    first_page: int | None = None,
    last_page: int | None = None,
) -> list[Image.Image]:
    """
    Convert PDF pages to PIL Images.

    Args:
        pdf_path: Path to PDF file or bytes content
        dpi: Resolution for rendering (default 300)
        first_page: First page to convert (1-indexed, None = first)
        last_page: Last page to convert (1-indexed, None = last)

    Returns:
        List of PIL Images, one per page
    """
    if isinstance(pdf_path, bytes):
        doc = fitz.open(stream=pdf_path, filetype="pdf")
    else:
        doc = fitz.open(pdf_path)

    images = []
    zoom = dpi / 72  # PDF default is 72 DPI
    matrix = fitz.Matrix(zoom, zoom)

    start = (first_page - 1) if first_page else 0
    end = last_page if last_page else len(doc)

    for page_num in range(start, min(end, len(doc))):
        page = doc[page_num]
        pix = page.get_pixmap(matrix=matrix)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)

    doc.close()
    return images


def get_pdf_page_count(pdf_path: str | Path | bytes) -> int:
    """Get the number of pages in a PDF."""
    if isinstance(pdf_path, bytes):
        doc = fitz.open(stream=pdf_path, filetype="pdf")
    else:
        doc = fitz.open(pdf_path)

    count = len(doc)
    doc.close()
    return count


def extract_pdf_metadata(pdf_path: str | Path | bytes) -> dict:
    """Extract metadata from PDF."""
    if isinstance(pdf_path, bytes):
        doc = fitz.open(stream=pdf_path, filetype="pdf")
    else:
        doc = fitz.open(pdf_path)

    metadata = doc.metadata or {}
    metadata["page_count"] = len(doc)

    doc.close()
    return metadata


def is_pdf(content: bytes) -> bool:
    """Check if content is a PDF by magic bytes."""
    return content[:4] == b"%PDF"
