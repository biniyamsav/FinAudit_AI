from pathlib import Path

import pdfplumber
import pypdfium2
from pydantic import BaseModel
from pypdf import PdfReader

from app.core.config import get_settings
from app.ingestion.common import ExtractionError, clean_text
from app.ingestion.ocr import ocr_image


class PageText(BaseModel):
    page: int
    text: str
    tables: list[list[list[str]]] = []
    needs_ocr: bool = False
    source: str = "text"
    ocr_confidence: float | None = None



class ExtractedDocument(BaseModel):
    schema_version: int = 4
    pages: list[PageText]

def _ocr_pages(path: Path, pages: list[PageText]) -> None:
    pdf = pypdfium2.PdfDocument(path)
    try:
        for item in pages:
            page = pdf[item.page - 1]
            try:
                image = page.render(scale=200 / 72).to_pil()
                lines = ocr_image(image)
            except Exception as error:
                raise ExtractionError("ocr_failed") from error
            finally:
                page.close()
            item.source = "ocr"
            if lines:
                item.text = "\n".join(line.text for line in lines)
                item.ocr_confidence = round(
                    sum(line.confidence for line in lines) / len(lines), 4
                )
                item.needs_ocr = False
    finally:
        pdf.close()

def extract_pdf_text(path: Path) -> ExtractedDocument:
    reader = PdfReader(path)
    page_count = len(reader.pages)
    max_pages = get_settings().extraction_max_pages
    if page_count > max_pages:
        raise ExtractionError("page_limit_exceeded")

    pages = []
    with pdfplumber.open(path) as plumber:
        for number, (page, plumber_page) in enumerate(
            zip(reader.pages, plumber.pages), start=1
        ):
            tables = [
                [[clean_text(cell) for cell in row] for row in table]
                for table in (plumber_page.extract_tables() or [])
            ]
            text = clean_text(page.extract_text())
            pages.append(
                PageText(
                    page=number,
                    text=text,
                    tables=tables,
                    needs_ocr=not text.strip(),
                )
            )
        scanned = [p for p in pages if p.needs_ocr]
    if len(scanned) > get_settings().extraction_max_ocr_pages:
        raise ExtractionError("ocr_page_limit_exceeded")
    if scanned:
        _ocr_pages(path, scanned)
    return ExtractedDocument(pages=pages)
