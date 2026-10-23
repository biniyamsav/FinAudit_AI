import uuid
from typing import Any, Dict, List

import pytest

from app.retrieval.context_builder import EMPTY_CONTEXT_MESSAGE, build_rag_context
from app.retrieval.reranking import rerank_chunks

COLLECTION = "DocumentChunk"


# --------------------------------------------------------------------------
# rerank_chunks -- pure, no Weaviate required
# --------------------------------------------------------------------------


def _dense(distance: float, chunk_id: str, **extra: Any) -> Dict[str, Any]:
    return {"chunk_id": chunk_id, "distance": distance, "text": chunk_id, **extra}


def _scored(score: float, chunk_id: str, **extra: Any) -> Dict[str, Any]:
    return {"chunk_id": chunk_id, "score": score, "text": chunk_id, **extra}


def test_rerank_sorts_dense_results_by_ascending_distance():
    chunks = [_dense(0.9, "c"), _dense(0.1, "a"), _dense(0.5, "b")]
    ranked = rerank_chunks(chunks)
    assert [c["chunk_id"] for c in ranked] == ["a", "b", "c"]


def test_rerank_sorts_scores_descending_and_normalises():
    ranked = rerank_chunks([_scored(2.0, "a"), _scored(10.0, "b")])
    assert [c["chunk_id"] for c in ranked] == ["b", "a"]
    # min-max normalisation maps the extremes onto 1.0 and 0.0
    assert ranked[0]["relevance"] == pytest.approx(1.0)
    assert ranked[-1]["relevance"] == pytest.approx(0.0)


def test_rerank_prefers_score_over_distance_when_both_present():
    # A dense hit at distance 0.0 must not outrank a much better BM25 score.
    chunks = [
        {"chunk_id": "dense", "distance": 0.0, "score": 1.0},
        {"chunk_id": "bm25", "distance": 5.0, "score": 50.0},
    ]
    ranked = rerank_chunks(chunks)
    assert ranked[0]["chunk_id"] == "bm25"


def test_rerank_drops_duplicate_chunk_ids_keeping_first():
    chunks = [
        _scored(5.0, "dup", document_id="doc1"),
        _scored(9.0, "dup", document_id="doc1"),
        _scored(1.0, "other"),
    ]
    ranked = rerank_chunks(chunks)
    assert [c["chunk_id"] for c in ranked] == ["dup", "other"]
    assert len(ranked) == 2


def test_rerank_dedupes_falls_back_to_document_and_text():
    chunks = [
        {"chunk_id": None, "document_id": "doc1", "text": "Revenue 1000", "score": 3.0},
        {"chunk_id": None, "document_id": "doc1", "text": "Revenue 1000", "score": 2.0},
        {"chunk_id": None, "document_id": "doc1", "text": "Cost 250", "score": 1.0},
    ]
    ranked = rerank_chunks(chunks)
    assert len(ranked) == 2
    assert ranked[0]["text"] == "Revenue 1000"


def test_rerank_respects_top_k():
    chunks = [_scored(float(10 - i), f"c{i}") for i in range(10)]
    assert len(rerank_chunks(chunks, top_k=3)) == 3


def test_rerank_handles_empty_and_non_positive_top_k():
    assert rerank_chunks([]) == []
    assert rerank_chunks([_scored(1.0, "a")], top_k=0) == []


def test_rerank_does_not_mutate_input_and_handles_missing_metadata():
    original = {"chunk_id": "a", "text": "Revenue"}
    ranked = rerank_chunks([original, {"chunk_id": "b", "text": "Cost"}])
    assert "relevance" not in original          # input untouched
    assert all(c["relevance"] >= 0 for c in ranked)  # missing score/distance -> 0.0
    assert [c["chunk_id"] for c in ranked] == ["a", "b"]  # ties keep input order


def test_rerank_keeps_dense_hits_comparable_among_themselves():
    ranked = rerank_chunks([_dense(0.2, "a"), _dense(0.8, "b")])
    assert ranked[0]["relevance"] > ranked[1]["relevance"]


# --------------------------------------------------------------------------
# build_rag_context -- pure, no Weaviate required
# --------------------------------------------------------------------------


def test_empty_context_uses_the_required_message():
    assert build_rag_context([]) == EMPTY_CONTEXT_MESSAGE
    assert build_rag_context([]) == "No relevant financial records found in workspace"


def test_pdf_chunk_renders_page_provenance_header():
    chunk = {
        "chunk_id": "doc1_p3_text",
        "document_id": "doc1",
        "text": "Total revenue 1500",
        # exactly what store_chunks_in_weaviate persists via str(provenance)
        "provenance": "{'source_type': 'pdf', 'page': 3}",
    }
    context = build_rag_context([chunk])
    assert "### Source 1" in context
    assert "`doc1`" in context
    assert "Page 3" in context
    assert "pdf" in context
    assert "Total revenue 1500" in context


def test_pdf_table_chunk_shows_table_index():
    chunk = {
        "document_id": "doc1",
        "text": "Table 2 on page 4:\nRevenue\t1500",
        "provenance": "{'source_type': 'pdf_table', 'page': 4, 'table_index': 2}",
    }
    context = build_rag_context([chunk])
    assert "Page 4" in context
    assert "Table 2" in context


def test_excel_chunk_shows_sheet_name():
    chunk = {
        "document_id": "doc2",
        "text": "Spreadsheet Sheet: P&L\nB1: 1500",
        "provenance": "{'source_type': 'excel', 'sheet': 'P&L'}",
    }
    context = build_rag_context([chunk])
    assert "Sheet P&L" in context
    assert "excel" in context
    assert "Page" not in context.split("---")[0]  # no fake page for a sheet


def test_dict_provenance_from_in_process_chunker_is_accepted():
    chunk = {
        "document_id": "doc3",
        "text": "Note 1000",
        "provenance": {"source_type": "docx"},
    }
    context = build_rag_context([chunk])
    assert "`doc3`" in context
    assert "docx" in context


def test_chunks_are_separated_and_numbered():
    chunks = [
        {"document_id": "d1", "text": "A", "provenance": {"source_type": "pdf", "page": 1}},
        {"document_id": "d2", "text": "B", "provenance": {"source_type": "pdf", "page": 2}},
    ]
    context = build_rag_context(chunks)
    assert "### Source 1" in context and "### Source 2" in context
    assert "\n\n---\n\n" in context


def test_unparseable_provenance_does_not_break_retrieval():
    chunk = {"document_id": "doc4", "text": "Revenue", "provenance": "not a dict"}
    context = build_rag_context([chunk])
    assert "`doc4`" in context
    assert "Revenue" in context


def test_blank_text_is_flagged_instead_of_rendering_empty():
    chunk = {"document_id": "doc5", "text": "   ", "provenance": {"source_type": "csv"}}
    assert "(no text extracted)" in build_rag_context([chunk])


# --------------------------------------------------------------------------
# search_workspace_keywords -- live local Weaviate
# --------------------------------------------------------------------------


def _connect():
    """Connect to the local Weaviate and ensure ``DocumentChunk`` exists.

    The collection definition mirrors what ``dense.store_chunks_in_weaviate``
    writes.  It is created on demand so the suite can run against a fresh
    Docker instance.
    """
    weaviate = pytest.importorskip(
        "weaviate", reason="weaviate-client is not installed"
    )
    try:
        client = weaviate.connect_to_local(host="localhost", port=8080, grpc_port=50051)
    except Exception as error:  # server down or too old for this client
        pytest.skip(f"local Weaviate is unavailable: {error}")

    if not client.collections.exists(COLLECTION):
        from weaviate.classes.config import Configure, DataType, Property

        # The running instance is 1.25.0 with no modules, so there is no
        # server-side vectorizer to use; dense/fusion supply their own vectors.
        client.collections.create(
            name=COLLECTION,
            vectorizer_config=Configure.Vectorizer.none(),
            properties=[
                Property(name="chunk_id", data_type=DataType.TEXT),
                Property(name="document_id", data_type=DataType.TEXT),
                Property(name="workspace_id", data_type=DataType.TEXT),
                Property(name="text", data_type=DataType.TEXT),
                Property(name="provenance", data_type=DataType.TEXT),
            ],
        )
    return client


def test_bm25_search_is_scoped_to_workspace():
    from app.retrieval.sparse import search_workspace_keywords

    client = _connect()
    created: List[str] = []
    try:
        collection = client.collections.get(COLLECTION)
        own_ws = f"ws-{uuid.uuid4()}"
        other_ws = f"ws-{uuid.uuid4()}"

        with collection.batch.fixed_size(batch_size=10) as batch:
            for workspace, text, marker in (
                (own_ws, "Account 4100-10 accrued revenue 1500", "OWN"),
                (other_ws, "Account 4100-10 accrued revenue 9999", "OTHER"),
            ):
                uuid_str = str(uuid.uuid4())
                created.append(uuid_str)
                batch.add_object(
                    uuid=uuid_str,
                    properties={
                        "chunk_id": f"{workspace}_{marker}",
                        "document_id": f"doc-{marker}",
                        "workspace_id": workspace,
                        "text": text,
                        "provenance": str(
                            {"source_type": "pdf", "page": 3}
                        ),
                    },
                )

        results = search_workspace_keywords(client, own_ws, "4100-10", limit=5)

        assert results, "expected the matching chunk to be returned"
        returned_texts = [r["text"] for r in results]
        assert any("1500" in t for t in returned_texts)
        assert all("9999" not in t for t in returned_texts)
        assert all(r["score"] is not None for r in results)
    finally:
        collection = client.collections.get(COLLECTION)
        for object_uuid in created:
            collection.data.delete_by_id(object_uuid)
        client.close()


def test_bm25_search_returns_empty_for_blank_query_and_rejects_missing_workspace():
    from app.retrieval.sparse import search_workspace_keywords

    client = _connect()
    try:
        assert search_workspace_keywords(client, f"ws-{uuid.uuid4()}", "   ") == []
        with pytest.raises(ValueError, match="workspace_id"):
            search_workspace_keywords(client, "", "revenue")
    finally:
        client.close()
