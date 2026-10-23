import csv
import io
from pathlib import Path

from pydantic import BaseModel

from app.core.config import get_settings
from app.ingestion.common import ExtractionError, clean_text


class CsvRow(BaseModel):
    row: int
    values: list[str]


class ExtractedCsv(BaseModel):
    schema_version: int = 1
    rows: list[CsvRow]


def extract_csv(path: Path) -> ExtractedCsv:
    text = path.read_bytes().decode("utf-8-sig").replace("\x00", "")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    max_rows = get_settings().extraction_max_rows
    rows: list[CsvRow] = []
    reader = csv.reader(io.StringIO(text), dialect)
    for number, values in enumerate(reader, start=1):
        if number > max_rows:
            raise ExtractionError("row_limit_exceeded")
        rows.append(CsvRow(row=number, values=[clean_text(value) for value in values]))
    return ExtractedCsv(rows=rows)
