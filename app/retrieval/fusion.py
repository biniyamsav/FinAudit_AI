import weaviate
from typing import List, Dict, Any

def hybrid_search(
    client: weaviate.Client,
    workspace_id: str,
    query_text: str,
    query_vector: List[float],
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Performs Weaviate hybrid search combining vector similarity and BM25 keyword matching,
    strictly bounded by workspace_id.
    """
    collection = client.collections.get("DocumentChunk")
    
    response = collection.query.hybrid(
        query=query_text,
        vector=query_vector,
        alpha=0.5,  # 0.5 balances keyword matching and semantic vector search equally
        limit=limit,
        filters=weaviate.classes.query.Filter.by_property("workspace_id").equal(workspace_id),
        return_metadata=weaviate.classes.query.MetadataQuery(score=True)
    )
    
    results = []
    for item in response.objects:
        results.append({
            "chunk_id": item.properties.get("chunk_id"),
            "document_id": item.properties.get("document_id"),
            "text": item.properties.get("text"),
            "provenance": item.properties.get("provenance"),
            "score": item.metadata.score
        })
        
    return results