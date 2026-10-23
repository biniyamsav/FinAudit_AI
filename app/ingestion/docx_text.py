from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from pydantic import BaseModel

from app.core.config import get_settings
from app.ingestion.common import ExtractionError, clean_text


class WordParagraph(BaseModel):
    paragraph_index: int
    text: str


class WordTable(BaseModel):
    paragraph_index: int
    rows: list[list[str]]


class ExtractedWord(BaseModel):
    schema_version: int = 1
    paragraphs: list[WordParagraph]
    tables: list[WordTable]


def extract_docx(path: Path) -> ExtractedWord:
    document = Document(path)
    max_rows = get_settings().extraction_max_rows
    paragraphs: list[WordParagraph] = []
    tables: list[WordTable] = []
    paragraph_index = 0
    table_rows = 0

    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            paragraph_index += 1
            text = clean_text(Paragraph(child, document).text)
            if text:
                paragraphs.append(
                    WordParagraph(paragraph_index=paragraph_index, text=text)
                )
        elif child.tag == qn("w:tbl"):
            table = Table(child, document)
            rows = [
                [clean_text(cell.text) for cell in row.cells] for row in table.rows
            ]
            table_rows += len(rows)
            if table_rows > max_rows:
                raise ExtractionError("row_limit_exceeded")
            tables.append(WordTable(paragraph_index=paragraph_index, rows=rows))

    return ExtractedWord(paragraphs=paragraphs, tables=tables)
