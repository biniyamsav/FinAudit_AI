from pathlib import Path

import pdfplumber
from pydantic import BaseModel
from pypdf import PdfReader


class PageText(BaseModel):
    page: int
    text: str
    tables: list[list[list[str]]] = []


class ExtractedDocument(BaseModel):
    schema_version: int = 2
    pages: list[PageText]


def _clean(value: str | None) -> str:
    return (value or "").replace("\x00", "")


def extract_pdf_text(path: Path) -> ExtractedDocument:
    reader = PdfReader(path)
    pages = []
    with pdfplumber.open(path) as plumber:
        for number, (page, plumber_page) in enumerate(
            zip(reader.pages, plumber.pages), start=1
        ):
            tables = [
                [[_clean(cell) for cell in row] for row in table]
                for table in plumber_page.extract_tables()
            ]
            pages.append(
                PageText(
                    page=number,
                    text=_clean(page.extract_text()),
                    tables=tables,
                )
            )
    return ExtractedDocument(pages=pages)