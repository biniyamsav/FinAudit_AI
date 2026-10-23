import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Document, ExtractedContent, IngestionJob
from app.db.session import get_session_factory
from app.main import app
from app.workers.ingestion_worker import process_document

client = TestClient(app)


def make_pdf(text: str) -> bytes:
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(objects) + 1,
        xref_at,
    )
    return out


def test_worker_extracts_pdf_text_and_deletes_temp_file():
    workspace_id = client.post("/api/v1/workspaces").json()["id"]
    files = {"file": ("r.pdf", make_pdf("Revenue 1000"), "application/pdf")}
    upload = client.post(f"/api/v1/workspaces/{workspace_id}/documents", files=files)
    document_id = uuid.UUID(upload.json()["id"])
    temp_file = Path(get_settings().temp_upload_dir) / workspace_id / str(document_id)
   
  

    with get_session_factory()() as db:
        document = db.get(Document, document_id)
        job = db.scalars(
            select(IngestionJob).where(IngestionJob.document_id == document_id)
        ).one()
        content = db.scalars(
            select(ExtractedContent).where(ExtractedContent.document_id == document_id)
        ).one()
        assert document.status == "ready"
        assert job.status == "succeeded"
        assert job.attempt_count == 1
        assert "Revenue 1000" in content.content["pages"][0]["text"]
    assert not temp_file.exists()