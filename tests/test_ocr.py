from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.ingestion.ocr import extract_ocr


def test_ocr_reads_text_from_image(tmp_path: Path):
    image = Image.new("RGB", (600, 120), "white")
    ImageDraw.Draw(image).text(
        (20, 30), "Revenue 1000", fill="black", font=ImageFont.load_default(size=48)
    )
    path = tmp_path / "scan"
    image.save(path, format="PNG")
    result = extract_ocr(path)
    assert "1000" in result.text
    assert result.mean_confidence is not None