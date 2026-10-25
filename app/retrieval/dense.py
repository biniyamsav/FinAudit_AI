import uuid
from weaviate.classes.init import Auth
from typing import List, Dict, Any

import weaviate

from app.core.config import get_settings
from weaviate.classes.config import Configure, DataType, Property, Tokenization

from app.retrieval.embeddings import embed_text


def get_weaviate_client() -> weaviate.WeaviateClient:
    settings = get_settings()
    if settings.weaviate_url:
        if settings.weaviate_api_key is None:
            raise RuntimeError("WEAVIATE_API_KEY is required when WEAVIATE_URL is set.")
        return weaviate.connect_to_weaviate_cloud(
            cluster_url=settings.weaviate_url,
            auth_credentials=Auth.api_key(settings.weaviate_api_key.get_secret_value()),
        )
    return weaviate.connect_to_local(
        host=settings.weaviate_host,
        port=settings.weaviate_http_port,
        grpc_port=settings.weaviate_grpc_port,
    )

def ensure_chunk_collection(client) -> None:
    if client.collections.exists("DocumentChunk"):
        return
    client.collections.create(
        "DocumentChunk",
        vectorizer_config=Configure.Vectorizer.none(),
        vector_index_config=Configure.VectorIndex.hfresh(),
        properties=[
            Property(name="chunk_id", data_type=DataType.TEXT, tokenization=Tokenization.FIELD),
            Property(name="document_id", data_type=DataType.TEXT, tokenization=Tokenization.FIELD),
            Property(name="workspace_id", data_type=DataType.TEXT, tokenization=Tokenization.FIELD),
            Property(name="text", data_type=DataType.TEXT),
            Property(name="provenance", data_type=DataType.TEXT),
        ],
    )
def store_chunks_in_weaviate(client: weaviate.Client, chunks: List[Any]):
    """
    Stores document chunks and their text directly into Weaviate.
    """
    ensure_chunk_collection(client)
    collection = client.collections.get("DocumentChunk")
    
    with collection.batch.dynamic() as batch:
        for chunk in chunks:
            # Deterministic uuid5 from the chunk id makes indexing idempotent:
            # a retried job overwrites the same object instead of creating a
            # duplicate chunk that would skew retrieval scores.
            batch.add_object(
                uuid=uuid.uuid5(uuid.NAMESPACE_URL, str(chunk.chunk_id)),
                properties={
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "workspace_id": chunk.workspace_id,
                    "text": chunk.text,
                    "provenance": str(chunk.provenance)
                },
                # Weaviate runs with vectorizer='none', so vectors must be
                # supplied here -- and from the same embedder used at query
                # time, or the two spaces would not be comparable.
                vector=embed_text(chunk.text),
            )

    # Weaviate's v4 batch API does NOT raise when objects are rejected -- it
    # only records them.  Surfacing them here is what lets the worker fail a
    # document instead of marking it ready while it is silently unsearchable.
    failures = list(collection.batch.failed_objects)
    if failures:
        raise RuntimeError(
            f"failed to index {len(failures)} chunk(s) into Weaviate"
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