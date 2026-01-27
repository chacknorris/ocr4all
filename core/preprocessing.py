from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
from PIL import Image


@dataclass
class PreprocessConfig:
    deskew: bool = True
    denoise: bool = True
    binarize: bool = True
    remove_borders: bool = False
    resize_factor: Optional[float] = None
    target_dpi: Optional[int] = 300


def preprocess_image(image: Image.Image, config: Optional[PreprocessConfig] = None) -> Image.Image:
    """Apply preprocessing pipeline to improve OCR accuracy."""
    if config is None:
        config = PreprocessConfig()

    img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if config.resize_factor:
        h, w = gray.shape[:2]
        new_w = int(w * config.resize_factor)
        new_h = int(h * config.resize_factor)
        gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    if config.deskew:
        gray = _deskew(gray)

    if config.denoise:
        gray = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)

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
    """Quick enhancement optimized for typical invoices/receipts."""
    config = PreprocessConfig(
        deskew=True,
        denoise=True,
        binarize=True,
        remove_borders=False,
    )
    return preprocess_image(image, config)
