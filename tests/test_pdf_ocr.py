from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.config import get_settings
from app.ingestion.common import ExtractionError
from app.ingestion.pdf_text import extract_pdf_text


def _build_pdf(page_texts: list[str]) -> bytes:
    """Minimal single-font PDF; an empty string yields a blank page."""
    count = len(page_texts)
    font_object = 3 + 2 * count
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [%s] /Count %d >>"
        % (b" ".join(b"%d 0 R" % (3 + i) for i in range(count)), count),
    }
    for index, text in enumerate(page_texts):
        content_object = 3 + count + index
        objects[3 + index] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents %d 0 R /Resources << /Font << /F1 %d 0 R >> >> >>"
            % (content_object, font_object)
        )
        content = (
            b"BT /F1 12 Tf 72 720 Td (%s) Tj ET" % text.encode() if text else b""
        )
        objects[content_object] = (
            b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream"
        )
    objects[font_object] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    out = b"%PDF-1.4\n"
    offsets = []
    for number in sorted(objects):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + objects[number] + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objects) + 1,
        xref_at,
    )
    return out


def test_image_only_pdf_is_extracted_by_ocr(tmp_path: Path):
    image = Image.new("RGB", (1200, 400), "white")
    ImageDraw.Draw(image).text(
        (40, 150),
        "TOTAL REVENUE 1500",
        fill="black",
        font=ImageFont.load_default(size=96),
    )
    path = tmp_path / "image_only.pdf"
    image.save(path, format="PDF")

    page = extract_pdf_text(path).pages[0]
    assert page.source == "ocr"
    assert page.needs_ocr is False
    assert "revenue" in page.text.lower()
    assert page.ocr_confidence is not None
    assert 0 < page.ocr_confidence <= 1


def test_mixed_pdf_keeps_text_page_and_ocrs_blank_page(tmp_path: Path):
    path = tmp_path / "mixed.pdf"
    path.write_bytes(_build_pdf(["Revenue 1000", ""]))

    pages = extract_pdf_text(path).pages
    assert len(pages) == 2

    text_page, blank_page = pages
    assert "Revenue 1000" in text_page.text
    assert text_page.source == "text"
    assert text_page.ocr_confidence is None

    assert blank_page.needs_ocr is True
    assert blank_page.text == ""
    assert blank_page.source == "ocr"
    assert blank_page.ocr_confidence is None


def test_ocr_page_limit_exceeded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(get_settings(), "extraction_max_ocr_pages", 1)
    path = tmp_path / "two_blank.pdf"
    path.write_bytes(_build_pdf(["", ""]))
    try:
        with pytest.raises(ExtractionError, match="ocr_page_limit_exceeded"):
            extract_pdf_text(path)
    finally:
        # drop the cached settings so the override cannot leak into later tests
        get_settings.cache_clear()
