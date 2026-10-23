from pathlib import Path

import pdfplumber
from pydantic import BaseModel
from pypdf import PdfReader

from app.core.config import get_settings
from app.ingestion.common import ExtractionError, clean_text


class PageText(BaseModel):
    page: int
    text: str
    tables: list[list[list[str]]] = []
    needs_ocr: bool = False


class ExtractedDocument(BaseModel):
    schema_version: int = 3
    pages: list[PageText]


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
    return ExtractedDocument(pages=pages)
