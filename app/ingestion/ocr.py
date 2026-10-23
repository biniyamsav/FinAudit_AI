from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image
from pydantic import BaseModel

from app.ingestion.common import ExtractionError, clean_text


class OcrLine(BaseModel):
    text: str
    confidence: float


class ExtractedImage(BaseModel):
    schema_version: int = 1
    text: str
    mean_confidence: float | None
    lines: list[OcrLine]


@lru_cache
def get_ocr_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def ocr_image(image: Image.Image) -> list[OcrLine]:
    result, _ = get_ocr_engine()(np.array(image.convert("RGB")))
    return [
        OcrLine(text=clean_text(text), confidence=float(score))
        for _box, text, score in (result or [])
    ]


def extract_ocr(path: Path) -> ExtractedImage:
    try:
        with Image.open(path) as image:
            lines = ocr_image(image)
    except Exception as error:
        raise ExtractionError("ocr_failed") from error
    mean = round(sum(line.confidence for line in lines) / len(lines), 4) if lines else None
    if not lines:
        raise ExtractionError("no_text_found")
    return ExtractedImage(
        text="\n".join(line.text for line in lines),
        mean_confidence=mean,
        lines=lines,
    )