from pathlib import Path

from app.ingestion.common import ExtractionError


def extract_ocr(_path: Path) -> None:
    """Images and scanned pages need OCR. No OCR library is installed yet."""
    raise ExtractionError("ocr_required")
