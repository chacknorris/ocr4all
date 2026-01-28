from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

import pytesseract
from PIL import Image
from pytesseract import Output

from core.config import get_settings
from core.preprocessing import PreprocessConfig, preprocess_image

settings = get_settings()

if settings.tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd


@dataclass
class OCRConfig:
    """
    Configuración de Tesseract OCR.

    PSM (Page Segmentation Mode):
        3 = Fully automatic page segmentation (RECOMENDADO)
        4 = Assume single column of text
        6 = Assume uniform block of text
        11 = Sparse text
        13 = Raw line

    OEM (OCR Engine Mode):
        0 = Legacy engine only
        1 = Neural nets LSTM engine only (RECOMENDADO con tessdata_best)
        2 = Legacy + LSTM
        3 = Default (based on available)
    """
    lang: str = "spa+eng"
    psm: int = 3  # Auto page segmentation - mejor para documentos variados
    oem: int = 1  # LSTM only - requiere tessdata_best para máxima precisión
    whitelist: str = ""
    preserve_interword_spaces: bool = True  # Mantener espacios entre palabras
    preprocess: PreprocessConfig = field(default_factory=PreprocessConfig)


@dataclass
class OCROutput:
    text: str
    confidence: Optional[float]
    word_data: Optional[list[dict]]
    processing_time_ms: int


def run_ocr(image: Image.Image, config: Optional[OCRConfig] = None) -> OCROutput:
    """
    Run OCR on an image with preprocessing.

    Args:
        image: PIL Image to process
        config: OCR configuration options

    Returns:
        OCROutput with text, confidence, word data, and timing
    """
    if config is None:
        config = OCRConfig(lang=settings.tesseract_lang)

    start_time = time.perf_counter()

    # Preprocess
    processed = preprocess_image(image, config.preprocess)

    # Build tesseract config string
    tess_config = _build_tesseract_config(config)

    # Run OCR
    text = pytesseract.image_to_string(processed, config=tess_config, lang=config.lang)

    # Get word-level data with confidence
    word_data, avg_confidence = _extract_word_data(processed, tess_config, config.lang)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    return OCROutput(
        text=text.strip(),
        confidence=avg_confidence,
        word_data=word_data,
        processing_time_ms=elapsed_ms,
    )


def _build_tesseract_config(config: OCRConfig) -> str:
    """Build tesseract CLI config string."""
    parts = [f"--psm {config.psm}", f"--oem {config.oem}"]

    if config.whitelist:
        parts.append(f"-c tessedit_char_whitelist={config.whitelist}")

    if config.preserve_interword_spaces:
        parts.append("-c preserve_interword_spaces=1")

    return " ".join(parts)


def _extract_word_data(
    image: Image.Image, tess_config: str, lang: str
) -> Tuple[list[dict], Optional[float]]:
    """Extract word-level OCR data with bounding boxes and confidence."""
    try:
        data = pytesseract.image_to_data(
            image, config=tess_config, lang=lang, output_type=Output.DICT
        )
    except Exception:
        return [], None

    words = []
    confidences = []

    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf = data["conf"][i]

        if not text:
            continue

        try:
            conf_val = int(conf)
        except (ValueError, TypeError):
            continue

        if conf_val < 0:
            continue

        confidences.append(conf_val)
        words.append({
            "text": text,
            "confidence": conf_val,
            "bbox": {
                "x": data["left"][i],
                "y": data["top"][i],
                "w": data["width"][i],
                "h": data["height"][i],
            },
            "block": data["block_num"][i],
            "line": data["line_num"][i],
            "word": data["word_num"][i],
        })

    avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else None

    return words, avg_conf


def run_ocr_raw(image: Image.Image, lang: str = "spa+eng") -> OCROutput:
    """
    Run OCR without any preprocessing.

    Ideal para:
    - PDFs con texto nativo (no escaneados)
    - Imágenes de alta calidad
    - Cuando el preprocessing está degradando la precisión

    Args:
        image: PIL Image to process
        lang: Language(s) for OCR

    Returns:
        OCROutput with text, confidence, word data, and timing
    """
    start_time = time.perf_counter()

    # Configuración optimizada para LSTM
    config = OCRConfig(
        lang=lang,
        psm=3,  # Auto
        oem=1,  # LSTM
        preserve_interword_spaces=True,
    )
    tess_config = _build_tesseract_config(config)

    # Convertir a RGB si es necesario (Tesseract lo maneja bien)
    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')

    # OCR directo sin preprocessing
    text = pytesseract.image_to_string(image, config=tess_config, lang=lang)

    # Word data
    word_data, avg_confidence = _extract_word_data(image, tess_config, lang)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    return OCROutput(
        text=text.strip(),
        confidence=avg_confidence,
        word_data=word_data,
        processing_time_ms=elapsed_ms,
    )


def get_tesseract_languages() -> list[str]:
    """Get list of available Tesseract languages."""
    try:
        langs = pytesseract.get_languages()
        return [l for l in langs if l != "osd"]
    except Exception:
        return ["eng", "spa"]


def get_tesseract_version() -> str:
    """Get Tesseract version string."""
    try:
        return pytesseract.get_tesseract_version().vstring
    except Exception:
        return "unknown"
