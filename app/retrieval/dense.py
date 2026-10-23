import weaviate
from typing import List, Dict, Any

def get_weaviate_client() -> weaviate.Client:
    """Connects to the local Weaviate instance running via Docker."""
    client = weaviate.connect_to_local(
        host="localhost",
        port=8080,
        grpc_port=50051
    )
    return client

def store_chunks_in_weaviate(client: weaviate.Client, chunks: List[Any]):
    """
    Stores document chunks and their text directly into Weaviate.
    """
    collection = client.collections.get("DocumentChunk")
    
    with collection.batch.dynamic() as batch:
        for chunk in chunks:
            batch.add_object(
                properties={
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "workspace_id": chunk.workspace_id,
                    "text": chunk.text,
                    "provenance": str(chunk.provenance)
                }
            )

def search_workspace_vectors(
    client: weaviate.Client, 
    workspace_id: str, 
    query_vector: List[float], 
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Performs a vector similarity search in Weaviate strictly bounded by workspace_id.
    """
    collection = client.collections.get("DocumentChunk")
    
    response = collection.query.near_vector(
        near_vector=query_vector,
        limit=limit,
        filters=weaviate.classes.query.Filter.by_property("workspace_id").equal(workspace_id),
        return_metadata=weaviate.classes.query.MetadataQuery(distance=True)
    )
    
    results = []
    for item in response.objects:
        results.append({
            "chunk_id": item.properties.get("chunk_id"),
            "document_id": item.properties.get("document_id"),
            "text": item.properties.get("text"),
            "provenance": item.properties.get("provenance"),
            "distance": item.metadata.distance
        })
        
    return results