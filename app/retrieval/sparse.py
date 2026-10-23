from typing import Any, Dict, List

import weaviate


def search_workspace_keywords(
    client: weaviate.WeaviateClient,
    workspace_id: str,
    query_text: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Run BM25 keyword search over ``DocumentChunk`` for a single workspace.

    Audit queries routinely hinge on exact strings -- an account code like
    ``4100-10``, a vendor name, a GL period label.  A dense vector search
    happily paraphrases those away, so a dedicated keyword path runs
    alongside ``dense.search_workspace_vectors`` and
    ``fusion.hybrid_search``.

    ``workspace_id`` is applied as a hard server-side filter, not sliced out
    afterwards: retrieval is multi-tenant, so a chunk belonging to another
    workspace must never enter the candidate set in the first place.  An
    empty ``workspace_id`` is rejected outright rather than downgraded to an
    unfiltered query, so a missing parameter cannot become a data leak.
    """
    if not workspace_id:
        raise ValueError("workspace_id is required to prevent cross-tenant leakage.")
    if not query_text.strip():
        return []

    collection = client.collections.get("DocumentChunk")

    response = collection.query.bm25(
        query=query_text,
        filters=weaviate.classes.query.Filter.by_property("workspace_id").equal(
            workspace_id
        ),
        limit=limit,
        return_metadata=weaviate.classes.query.MetadataQuery(score=True),
    )

    results: List[Dict[str, Any]] = []
    for item in response.objects:
        results.append(
            {
                "chunk_id": item.properties.get("chunk_id"),
                "document_id": item.properties.get("document_id"),
                "text": item.properties.get("text"),
                "provenance": item.properties.get("provenance"),
                "score": item.metadata.score,
            }
        )

    return results
