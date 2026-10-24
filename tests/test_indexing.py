import math

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.ingestion.chunking import chunk_document
from app.main import app
from app.retrieval.embeddings import EMBEDDING_DIM, embed_text
from app.retrieval.sparse import search_workspace_keywords
from tests.test_worker import make_pdf

client = TestClient(app)


# --------------------------------------------------------------------------
# embeddings
# --------------------------------------------------------------------------


def test_embed_text_is_deterministic_and_unit_length():
    first = embed_text("Total revenue 1500 USD")
    second = embed_text("Total revenue 1500 USD")
    assert first == second
    assert len(first) == EMBEDDING_DIM
    assert math.isclose(math.sqrt(sum(v * v for v in first)), 1.0, rel_tol=1e-9)


def test_embed_text_shared_words_score_higher_than_unrelated_ones():
    query = embed_text("revenue recognition policy")
    related = embed_text("The revenue recognition policy is described here.")
    unrelated = embed_text("Office lease terminated after relocation.")
    cosine = lambda a, b: sum(x * y for x, y in zip(a, b))  # unit vectors
    assert cosine(query, related) > cosine(query, unrelated)


def test_embed_text_handles_empty_input():
    vector = embed_text("")
    assert len(vector) == EMBEDDING_DIM
    assert set(vector) == {0.0}


# --------------------------------------------------------------------------
# chunking against the shapes the extractors really produce
# --------------------------------------------------------------------------


def test_chunk_pdf_text_and_tables():
    content = {
        "schema_version": 4,
        "pages": [
            {
                "page": 3,
                "text": "Revenue grew this quarter.",
                # extract_pdf_text: list[list[list[str]]]
                "tables": [[["Revenue", "1500"], ["COGS", "600"]]],
                "needs_ocr": False,
                "source": "text",
                "ocr_confidence": None,
            }
        ],
    }
    chunks = chunk_document("doc1", "ws1", ".pdf", content)
    texts = {c.chunk_id: c.text for c in chunks}

    assert texts["doc1_p3_text"] == "Revenue grew this quarter."
    table = texts["doc1_p3_table_0"]
    assert "Revenue\t1500" in table
    assert "COGS\t600" in table
    assert "Table 0 on page 3" in table
    table_chunk = next(c for c in chunks if c.chunk_id == "doc1_p3_table_0")
    assert table_chunk.provenance == {"source_type": "pdf_table", "page": 3, "table_index": 0}


def test_chunk_csv_uses_values_not_none():
    # extract_csv yields {"row": int, "values": [...]} -- the old code read a
    # "data" key that never existed and produced "Row 1: None".
    content = {
        "schema_version": 1,
        "rows": [{"row": 1, "values": ["Revenue", "1000"]}],
    }
    chunks = chunk_document("doc2", "ws1", ".csv", content)
    assert len(chunks) == 1
    assert chunks[0].text == "Row 1: Revenue, 1000"
    assert "None" not in chunks[0].text


def test_chunk_empty_csv_produces_nothing():
    assert chunk_document("doc3", "ws1", ".csv", {"rows": []}) == []


def test_chunk_excel_groups_cells_by_sheet():
    content = {
        "cells": [
            {"sheet": "P&L", "cell": "B7", "value": "1,234.50"},
            {"sheet": "P&L", "cell": "C3", "value": "Revenue"},
        ]
    }
    chunks = chunk_document("doc4", "ws1", ".xlsx", content)
    assert len(chunks) == 1
    assert chunks[0].provenance == {"source_type": "excel", "sheet": "P&L"}
    assert "B7: 1,234.50" in chunks[0].text


# --------------------------------------------------------------------------
# end to end: upload -> extract -> chunk -> indexed in Weaviate
# --------------------------------------------------------------------------


def _weaviate():
    from app.retrieval.dense import get_weaviate_client

    return get_weaviate_client()


def test_uploaded_pdf_is_indexed_in_weaviate():
    client_w = _weaviate()
    try:
        workspace_id = client.post("/api/v1/workspaces").json()["id"]
        files = {"file": ("revenue.pdf", make_pdf("Revenue 1500"), "application/pdf")}
        assert (
            client.post(f"/api/v1/workspaces/{workspace_id}/documents", files=files).status_code
            == 201
        )
        results = search_workspace_keywords(client_w, workspace_id, "Revenue", limit=5)
        assert results, "PDF text chunk was not indexed"
        assert any("1500" in (r["text"] or "") for r in results)
        assert all(r["document_id"] for r in results)
    finally:
        client_w.close()


def test_uploaded_csv_is_indexed_in_weaviate():
    client_w = _weaviate()
    try:
        workspace_id = client.post("/api/v1/workspaces").json()["id"]
        files = {"file": ("data.csv", b"Revenue,1000\n", "text/csv")}
        assert (
            client.post(f"/api/v1/workspaces/{workspace_id}/documents", files=files).status_code
            == 201
        )
        results = search_workspace_keywords(client_w, workspace_id, "Revenue", limit=5)
        assert results, "CSV row chunk was not indexed"
        assert any("1000" in (r["text"] or "") for r in results)
    finally:
        client_w.close()


def test_uploaded_xlsx_is_indexed_in_weaviate():
    client_w = _weaviate()
    try:
        workspace_id = client.post("/api/v1/workspaces").json()["id"]
        book = Workbook()
        book.active.title = "P&L"
        book.active["A1"] = "1000"
        from io import BytesIO

        buffer = BytesIO()
        book.save(buffer)
        files = {
            "file": ("book.xlsx", buffer.getvalue(), "application/octet-stream")
        }
        assert (
            client.post(f"/api/v1/workspaces/{workspace_id}/documents", files=files).status_code
            == 201
        )
        results = search_workspace_keywords(client_w, workspace_id, "P&L", limit=5)
        assert results, "Excel sheet chunk was not indexed"
    finally:
        client_w.close()
