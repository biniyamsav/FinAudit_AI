from pathlib import Path

from pydantic import BaseModel
from pypdf import PdfReader


class PageText(BaseModel):
    page: int
    text: str


class ExtractedDocument(BaseModel):
    schema_version: int = 1
    pages: list[PageText]


def extract_pdf_text(path: Path) -> ExtractedDocument:
    reader = PdfReader(path)
    pages = [
        PageText(page=number, text=(page.extract_text() or "").replace("\x00", ""))
        for number, page in enumerate(reader.pages, start=1)
    ]
    return ExtractedDocument(pages=pages)