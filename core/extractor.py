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

    # Limpiar espacios
    value = value.strip()

    # Meses en español -> número
    MESES = {
        "ene": "01", "enero": "01",
        "feb": "02", "febrero": "02",
        "mar": "03", "marzo": "03",
        "abr": "04", "abril": "04",
        "may": "05", "mayo": "05",
        "jun": "06", "junio": "06",
        "jul": "07", "julio": "07",
        "ago": "08", "agosto": "08",
        "sep": "09", "sept": "09", "septiembre": "09",
        "oct": "10", "octubre": "10",
        "nov": "11", "noviembre": "11",
        "dic": "12", "diciembre": "12",
    }

    # Try common formats
    patterns = [
        # YYYY-MM-DD (ya normalizado)
        (r"^(\d{4})-(\d{2})-(\d{2})$", lambda m: f"{m.group(1)}-{m.group(2)}-{m.group(3)}"),
        # DD/MM/YYYY o DD-MM-YYYY
        (r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$",
         lambda m: f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"),
        # DD/MM/YY o DD-MM-YY
        (r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2})$",
         lambda m: f"20{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"),
    ]

    for pattern, replacement in patterns:
        match = re.match(pattern, value)
        if match:
            return replacement(match)

    # Intentar formato con mes en texto: "06 de abril de 2021" o "6 abril 2021"
    mes_pattern = r"(\d{1,2})\s*(?:de\s+)?([a-zA-Z]+)\s*(?:de\s+)?(\d{2,4})"
    match = re.match(mes_pattern, value, re.IGNORECASE)
    if match:
        dia = match.group(1).zfill(2)
        mes_texto = match.group(2).lower()
        año = match.group(3)

        if len(año) == 2:
            año = f"20{año}"

        # Buscar el mes
        for mes_key, mes_num in MESES.items():
            if mes_texto.startswith(mes_key):
                return f"{año}-{mes_num}-{dia}"

    return value


POST_PROCESSORS = {
    "normalize_rut": normalize_rut,
    "normalize_currency": normalize_currency,
    "normalize_date": normalize_date,
}


# =============================================================================
# PATRONES INTELIGENTES DE FALLBACK
# =============================================================================

# Patrones de fecha (ordenados por especificidad)
DATE_PATTERNS = [
    # Con etiqueta explícita (mayor confianza)
    (r"FECHA\s*(?:DE\s*)?(?:EMISI[OÓ]N)?[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", 0.95),
    (r"FECHA[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", 0.95),
    (r"FEC\.?\s*EMIS\.?[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", 0.90),
    # Formato ISO
    (r"(\d{4}-\d{2}-\d{2})", 0.85),
    # Fecha con mes en texto
    (r"(\d{1,2}\s+(?:de\s+)?(?:ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|abr(?:il)?|may(?:o)?|jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:tiembre)?|oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)\s+(?:de\s+)?(?:20)?\d{2})", 0.85),
    # Fallback: cualquier fecha DD-MM-YYYY o DD/MM/YYYY
    (r"(\d{1,2}[/-]\d{1,2}[/-](?:19|20)\d{2})", 0.75),
    # Fallback: fecha corta DD-MM-YY
    (r"(\d{1,2}[/-]\d{1,2}[/-]\d{2})(?!\d)", 0.70),
]

# Patrones de montos/totales (ordenados por especificidad)
CURRENCY_PATTERNS = [
    # Con etiqueta explícita
    (r"TOTAL\s*(?:A\s*PAGAR)?[:\s]*\$?\s*([\d.,]+)", 0.95),
    (r"TOTAL[:\s]*\$?\s*([\d.,]+)", 0.95),
    (r"MONTO\s*TOTAL[:\s]*\$?\s*([\d.,]+)", 0.95),
    (r"VALOR\s*TOTAL[:\s]*\$?\s*([\d.,]+)", 0.90),
    (r"IMPORTE\s*TOTAL[:\s]*\$?\s*([\d.,]+)", 0.90),
    # Neto/IVA
    (r"(?:MONTO\s*)?NETO[:\s]*\$?\s*([\d.,]+)", 0.90),
    (r"I\.?V\.?A\.?\s*(?:\(\d+%\))?[:\s]*\$?\s*([\d.,]+)", 0.90),
    (r"SUBTOTAL[:\s]*\$?\s*([\d.,]+)", 0.85),
    # Fallback: monto con símbolo $
    (r"\$\s*([\d.,]{3,})", 0.70),
]

# Patrones de RUT
RUT_PATTERNS = [
    # Con etiqueta
    (r"R\.?U\.?T\.?\s*(?:EMISOR)?[:\s]*(\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK])", 0.95),
    (r"RUT[:\s]*(\d{1,2}\.?\d{3}\.?\d{3}-?[\dkK])", 0.95),
    # Fallback: formato RUT sin etiqueta
    (r"(\d{1,2}\.\d{3}\.\d{3}-[\dkK])", 0.85),
    (r"(\d{7,8}-[\dkK])", 0.75),
]

# Patrones de número de documento
DOC_NUMBER_PATTERNS = [
    (r"(?:BOLETA|FACTURA|GU[IÍ]A)\s*(?:ELECTR[OÓ]NICA)?\s*N[°º]?\s*[:\s]*(\d+)", 0.95),
    (r"N[°º]\s*(?:BOLETA|FACTURA|DOCUMENTO)?[:\s]*(\d+)", 0.90),
    (r"FOLIO[:\s]*(\d+)", 0.90),
    (r"DOC(?:UMENTO)?\.?\s*N[°º]?[:\s]*(\d+)", 0.85),
]


def extract_with_fallback(
    text: str,
    patterns: list[tuple[str, float]],
    post_processor: Optional[str] = None,
) -> Tuple[Optional[str], float]:
    """
    Intenta extraer un valor usando múltiples patrones en orden de prioridad.

    Args:
        text: Texto OCR
        patterns: Lista de (patrón_regex, confianza_base)
        post_processor: Nombre del post-procesador a aplicar

    Returns:
        (valor_extraído, confianza) o (None, 0.0)
    """
    for pattern, base_confidence in patterns:
        try:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip()
                if value:
                    # Aplicar post-procesamiento si existe
                    if post_processor and post_processor in POST_PROCESSORS:
                        value = POST_PROCESSORS[post_processor](value)
                    return value, base_confidence
        except re.error:
            continue

    return None, 0.0


def smart_extract_date(text: str) -> Tuple[Optional[str], float]:
    """Extrae fecha usando patrones inteligentes con fallback."""
    return extract_with_fallback(text, DATE_PATTERNS, "normalize_date")


def smart_extract_total(text: str) -> Tuple[Optional[str], float]:
    """Extrae monto total usando patrones inteligentes con fallback."""
    return extract_with_fallback(text, CURRENCY_PATTERNS, "normalize_currency")


def smart_extract_rut(text: str) -> Tuple[Optional[str], float]:
    """Extrae RUT usando patrones inteligentes con fallback."""
    return extract_with_fallback(text, RUT_PATTERNS, "normalize_rut")


def smart_extract_doc_number(text: str) -> Tuple[Optional[str], float]:
    """Extrae número de documento usando patrones inteligentes."""
    return extract_with_fallback(text, DOC_NUMBER_PATTERNS, None)


def extract_field(
    text: str,
    pattern: str,
    field_type: FieldType = FieldType.TEXT,
    flags: str = "IGNORECASE",
    post_processing: Optional[str] = None,
    field_name: Optional[str] = None,
    use_fallback: bool = True,
) -> Tuple[Optional[str], float]:
    """
    Extract a single field from text using regex pattern.

    Si el patrón principal no encuentra el valor y use_fallback=True,
    intenta usar patrones inteligentes basados en el tipo de campo.

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
        match = None

    if match:
        # Get captured group or full match
        value = match.group(1) if match.groups() else match.group(0)
        value = value.strip()

        # Apply post-processing
        if post_processing and post_processing in POST_PROCESSORS:
            value = POST_PROCESSORS[post_processing](value)

        # Calculate confidence based on field type validation
        confidence = _calculate_confidence(value, field_type)
        return value, confidence

    # === FALLBACK: Si el patrón principal no encontró nada ===
    if use_fallback:
        fallback_value, fallback_conf = _try_smart_fallback(
            text, field_type, field_name
        )
        if fallback_value:
            return fallback_value, fallback_conf

    return None, 0.0


def _try_smart_fallback(
    text: str,
    field_type: FieldType,
    field_name: Optional[str] = None,
) -> Tuple[Optional[str], float]:
    """
    Intenta extraer el campo usando patrones inteligentes de fallback.

    Esto se activa cuando el patrón del template no encuentra el valor.
    """
    # Determinar qué tipo de extracción usar
    field_name_lower = (field_name or "").lower()

    # Fecha
    if field_type == FieldType.DATE or "fecha" in field_name_lower:
        return smart_extract_date(text)

    # Montos/Total
    if field_type == FieldType.CURRENCY or any(
        kw in field_name_lower for kw in ["total", "monto", "neto", "iva", "subtotal"]
    ):
        return smart_extract_total(text)

    # RUT
    if field_type == FieldType.RUT or "rut" in field_name_lower:
        return smart_extract_rut(text)

    # Número de documento
    if any(kw in field_name_lower for kw in ["numero", "folio", "boleta", "factura"]):
        return smart_extract_doc_number(text)

    return None, 0.0


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
    use_fallback: bool = True,
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
        use_fallback: Si True, usa patrones inteligentes cuando el patrón principal falla

    Returns:
        List of ExtractedField results
    """
    results = []

    for field_def in template_fields:
        field_name = field_def["name"]

        value, confidence = extract_field(
            text=text,
            pattern=field_def["pattern"],
            field_type=FieldType(field_def.get("field_type", "text")),
            flags=field_def.get("pattern_flags", "IGNORECASE"),
            post_processing=field_def.get("post_processing"),
            field_name=field_name,
            use_fallback=use_fallback,
        )

        results.append(ExtractedField(
            field_name=field_name,
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
