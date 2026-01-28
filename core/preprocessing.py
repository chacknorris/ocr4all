from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
from PIL import Image


@dataclass
class PreprocessConfig:
    """
    Configuración de preprocesamiento de imagen.

    IMPORTANTE: Con tessdata_best y Tesseract 5 LSTM, el preprocesamiento
    agresivo generalmente REDUCE la precisión. Los valores por defecto
    están optimizados para máxima precisión.
    """
    deskew: bool = False  # Solo activar si documento está rotado
    denoise: bool = False  # LSTM maneja ruido mejor que denoising agresivo
    binarize: bool = False  # CRÍTICO: LSTM funciona mejor con escala de grises
    remove_borders: bool = False
    resize_factor: Optional[float] = None
    target_dpi: Optional[int] = None  # None = mantener resolución original
    convert_to_grayscale: bool = True  # Convertir a escala de grises (recomendado)
    normalize_contrast: bool = True  # Normalización suave de contraste


def preprocess_image(image: Image.Image, config: Optional[PreprocessConfig] = None) -> Image.Image:
    """
    Apply preprocessing pipeline to improve OCR accuracy.

    Con tessdata_best y LSTM, menos es más. El preprocesamiento agresivo
    (especialmente binarización) puede REDUCIR la precisión.
    """
    if config is None:
        config = PreprocessConfig()

    # Convertir a numpy array
    img = np.array(image)

    # Convertir a escala de grises si es necesario
    if config.convert_to_grayscale:
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img
    else:
        # Mantener color pero trabajar con copia
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2BGR) if len(img.shape) == 3 else img

    # Resize si se especifica factor
    if config.resize_factor:
        h, w = gray.shape[:2]
        new_w = int(w * config.resize_factor)
        new_h = int(h * config.resize_factor)
        gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    # Normalización suave de contraste (CLAHE) - mejora sin destruir detalles
    if config.normalize_contrast and len(gray.shape) == 2:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)

    # Deskew solo si está activado explícitamente
    if config.deskew:
        gray = _deskew(gray)

    # Denoising suave (solo si está activado - generalmente no recomendado)
    if config.denoise:
        # Usar parámetros menos agresivos
        gray = cv2.fastNlMeansDenoising(gray, None, h=5, templateWindowSize=7, searchWindowSize=21)

    # Binarización (solo si está activada - NO recomendado para LSTM)
    if config.binarize:
        gray = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=11,
            C=2,
        )

    if config.remove_borders:
        gray = _remove_borders(gray)

    return Image.fromarray(gray)


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Correct image skew/rotation."""
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))

    if coords.size == 0:
        return gray

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) < 0.5:
        return gray

    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return rotated


def _remove_borders(gray: np.ndarray) -> np.ndarray:
    """Remove black borders from scanned documents."""
    contours, _ = cv2.findContours(gray, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return gray

    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)

    if w < 50 or h < 50:
        return gray

    return gray[y : y + h, x : x + w]


def enhance_for_ocr(image: Image.Image) -> Image.Image:
    """
    Quick enhancement optimized for typical invoices/receipts.

    Usa configuración mínima optimizada para tessdata_best + LSTM.
    """
    config = PreprocessConfig(
        deskew=False,
        denoise=False,
        binarize=False,  # CRÍTICO: no binarizar para LSTM
        remove_borders=False,
        convert_to_grayscale=True,
        normalize_contrast=True,
    )
    return preprocess_image(image, config)


def preprocess_for_poor_quality(image: Image.Image) -> Image.Image:
    """
    Preprocesamiento para documentos de mala calidad (fotos, escaneos malos).

    Solo usar cuando el documento tiene problemas visibles de calidad.
    """
    config = PreprocessConfig(
        deskew=True,
        denoise=True,  # Denoising suave
        binarize=False,  # Aún así, no binarizar
        remove_borders=True,
        convert_to_grayscale=True,
        normalize_contrast=True,
    )
    return preprocess_image(image, config)
