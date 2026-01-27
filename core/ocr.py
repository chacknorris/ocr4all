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
    lang: str = "spa+eng"
    psm: int = 6  # Assume uniform block of text
    oem: int = 1  # LSTM only
    whitelist: str = ""
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
