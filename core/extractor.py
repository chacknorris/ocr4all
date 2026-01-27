from __future__ import annotations
"""
Metadata extraction engine with configurable templates.
"""
import re
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from models.document import FieldType


@dataclass
class ExtractedField:
    field_name: str
    value: Optional[str]
    confidence: float
    source_page: Optional[int] = None
    raw_match: Optional[str] = None


# Post-processing functions
def normalize_rut(value: str) -> str:
    """Normalize Chilean RUT format to XX.XXX.XXX-X"""
    if not value:
        return value
    # Remove all non-alphanumeric
    clean = re.sub(r"[^\dkK]", "", value.upper())
    if len(clean) < 8:
        return value
    # Format
    body = clean[:-1]
    dv = clean[-1]
    # Add dots
    formatted = ""
    for i, char in enumerate(reversed(body)):
        if i > 0 and i % 3 == 0:
            formatted = "." + formatted
        formatted = char + formatted
    return f"{formatted}-{dv}"


def normalize_currency(value: str) -> str:
    """Normalize currency values, removing symbols and formatting."""
    if not value:
        return value
    # Remove $ and spaces
    clean = re.sub(r"[$\s]", "", value)
    # Replace comma decimal separator with dot
    clean = clean.replace(".", "").replace(",", ".")
    try:
        num = float(clean)
        return str(int(num)) if num == int(num) else str(num)
    except ValueError:
        return value


def normalize_date(value: str) -> str:
    """Normalize date to YYYY-MM-DD format."""
    if not value:
        return value

    # Try common Chilean formats
    patterns = [
        (r"(\d{2})[/-](\d{2})[/-](\d{4})", r"\3-\2-\1"),  # DD/MM/YYYY -> YYYY-MM-DD
        (r"(\d{2})[/-](\d{2})[/-](\d{2})", lambda m: f"20{m.group(3)}-{m.group(2)}-{m.group(1)}"),  # DD/MM/YY
    ]

    for pattern, replacement in patterns:
        match = re.match(pattern, value)
        if match:
            if callable(replacement):
                return replacement(match)
            return re.sub(pattern, replacement, value)

    return value


POST_PROCESSORS = {
    "normalize_rut": normalize_rut,
    "normalize_currency": normalize_currency,
    "normalize_date": normalize_date,
}


def extract_field(
    text: str,
    pattern: str,
    field_type: FieldType = FieldType.TEXT,
    flags: str = "IGNORECASE",
    post_processing: Optional[str] = None,
) -> Tuple[Optional[str], float]:
    """
    Extract a single field from text using regex pattern.

    Returns:
        Tuple of (extracted_value, confidence)
    """
    # Build regex flags
    re_flags = 0
    if "IGNORECASE" in flags:
        re_flags |= re.IGNORECASE
    if "MULTILINE" in flags:
        re_flags |= re.MULTILINE
    if "DOTALL" in flags:
        re_flags |= re.DOTALL

    try:
        match = re.search(pattern, text, re_flags)
    except re.error:
        return None, 0.0

    if not match:
        return None, 0.0

    # Get captured group or full match
    value = match.group(1) if match.groups() else match.group(0)
    value = value.strip()

    # Apply post-processing
    if post_processing and post_processing in POST_PROCESSORS:
        value = POST_PROCESSORS[post_processing](value)

    # Calculate confidence based on field type validation
    confidence = _calculate_confidence(value, field_type)

    return value, confidence


def _calculate_confidence(value: str, field_type: FieldType) -> float:
    """Calculate extraction confidence based on value and expected type."""
    if not value:
        return 0.0

    base_confidence = 0.7

    if field_type == FieldType.RUT:
        # Validate RUT format
        if re.match(r"^\d{1,2}\.\d{3}\.\d{3}-[\dkK]$", value):
            return 0.95
        elif re.match(r"^\d{7,9}-?[\dkK]$", value):
            return 0.8
        return 0.5

    elif field_type == FieldType.NUMBER or field_type == FieldType.CURRENCY:
        # Check if it's a valid number
        clean = re.sub(r"[^\d.,]", "", value)
        try:
            float(clean.replace(",", "."))
            return 0.9
        except ValueError:
            return 0.5

    elif field_type == FieldType.DATE:
        # Check common date formats
        if re.match(r"\d{4}-\d{2}-\d{2}", value):
            return 0.95
        elif re.match(r"\d{2}[/-]\d{2}[/-]\d{2,4}", value):
            return 0.85
        return 0.6

    return base_confidence


def extract_with_template(
    text: str,
    template_fields: list[dict],
) -> list[ExtractedField]:
    """
    Extract all fields defined in a template.

    Args:
        text: Full OCR text
        template_fields: List of field definitions with keys:
            - name: Field name
            - pattern: Regex pattern
            - field_type: FieldType enum value
            - pattern_flags: Regex flags string
            - post_processing: Optional post-processor name

    Returns:
        List of ExtractedField results
    """
    results = []

    for field_def in template_fields:
        value, confidence = extract_field(
            text=text,
            pattern=field_def["pattern"],
            field_type=FieldType(field_def.get("field_type", "text")),
            flags=field_def.get("pattern_flags", "IGNORECASE"),
            post_processing=field_def.get("post_processing"),
        )

        results.append(ExtractedField(
            field_name=field_def["name"],
            value=value,
            confidence=confidence,
        ))

    return results


def classify_document(text: str, templates: list[dict]) -> Optional[str]:
    """
    Classify document based on keyword matching against templates.

    Args:
        text: OCR text
        templates: List of template dicts with 'code', 'classification_keywords', 'priority'

    Returns:
        Template code of best match, or None
    """
    text_upper = text.upper()

    # Sort by priority (higher first)
    sorted_templates = sorted(templates, key=lambda t: t.get("priority", 0), reverse=True)

    best_match = None
    best_score = 0

    for template in sorted_templates:
        keywords = template.get("classification_keywords", [])
        if not keywords:
            continue

        score = sum(1 for kw in keywords if kw.upper() in text_upper)

        if score > best_score:
            best_score = score
            best_match = template.get("code")

    return best_match if best_score > 0 else None


# Default templates (fallback when DB is empty)
DEFAULT_TEMPLATES = {
    "boleta": {
        "name": "Boleta Electrónica",
        "code": "boleta",
        "doc_type": "boleta",
        "classification_keywords": ["BOLETA ELECTRÓNICA", "BOLETA ELECTRONICA", "DTE"],
        "fields": [
            {
                "name": "rut_emisor",
                "label": "RUT Emisor",
                "field_type": "rut",
                "pattern": r"RUT[:\s]*(\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK])",
                "post_processing": "normalize_rut",
                "required": True,
            },
            {
                "name": "numero_boleta",
                "label": "N° Boleta",
                "field_type": "number",
                "pattern": r"(?:BOLETA|N[°º])\s*[:\s]*(\d+)",
            },
            {
                "name": "fecha",
                "label": "Fecha",
                "field_type": "date",
                "pattern": r"FECHA[:\s]*(\d{2}[/-]\d{2}[/-]\d{2,4})",
                "post_processing": "normalize_date",
            },
            {
                "name": "total",
                "label": "Total",
                "field_type": "currency",
                "pattern": r"TOTAL[:\s$]*[\$]?\s*(\d+[\.,]?\d*)",
                "post_processing": "normalize_currency",
                "required": True,
            },
        ],
    },
    "factura": {
        "name": "Factura Electrónica",
        "code": "factura",
        "doc_type": "factura",
        "classification_keywords": ["FACTURA ELECTRÓNICA", "FACTURA ELECTRONICA", "FACTURA AFECTA"],
        "fields": [
            {
                "name": "rut_emisor",
                "label": "RUT Emisor",
                "field_type": "rut",
                "pattern": r"RUT[:\s]*(\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK])",
                "post_processing": "normalize_rut",
                "required": True,
            },
            {
                "name": "rut_receptor",
                "label": "RUT Receptor",
                "field_type": "rut",
                "pattern": r"(?:RUT|R\.U\.T\.?)\s*(?:RECEPTOR|CLIENTE)[:\s]*(\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK])",
                "post_processing": "normalize_rut",
            },
            {
                "name": "numero_factura",
                "label": "N° Factura",
                "field_type": "number",
                "pattern": r"FACTURA[^0-9]*N[°º]?\s*(\d+)",
            },
            {
                "name": "fecha_emision",
                "label": "Fecha Emisión",
                "field_type": "date",
                "pattern": r"FECHA[:\s]*(\d{2}[/-]\d{2}[/-]\d{2,4})",
                "post_processing": "normalize_date",
            },
            {
                "name": "neto",
                "label": "Neto",
                "field_type": "currency",
                "pattern": r"NETO[:\s$]*[\$]?\s*(\d+[\.,]?\d*)",
                "post_processing": "normalize_currency",
            },
            {
                "name": "iva",
                "label": "IVA",
                "field_type": "currency",
                "pattern": r"I\.?V\.?A\.?[:\s$]*[\$]?\s*(\d+[\.,]?\d*)",
                "post_processing": "normalize_currency",
            },
            {
                "name": "total",
                "label": "Total",
                "field_type": "currency",
                "pattern": r"TOTAL[:\s$]*[\$]?\s*(\d+[\.,]?\d*)",
                "post_processing": "normalize_currency",
                "required": True,
            },
        ],
    },
    "guia_despacho": {
        "name": "Guía de Despacho",
        "code": "guia_despacho",
        "doc_type": "guia_despacho",
        "classification_keywords": ["GUÍA DE DESPACHO", "GUIA DE DESPACHO"],
        "fields": [
            {
                "name": "rut_emisor",
                "label": "RUT Emisor",
                "field_type": "rut",
                "pattern": r"RUT[:\s]*(\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK])",
                "post_processing": "normalize_rut",
                "required": True,
            },
            {
                "name": "numero_guia",
                "label": "N° Guía",
                "field_type": "number",
                "pattern": r"GU[IÍ]A[^0-9]*N[°º]?\s*(\d+)",
            },
            {
                "name": "fecha",
                "label": "Fecha",
                "field_type": "date",
                "pattern": r"FECHA[:\s]*(\d{2}[/-]\d{2}[/-]\d{2,4})",
                "post_processing": "normalize_date",
            },
        ],
    },
}
