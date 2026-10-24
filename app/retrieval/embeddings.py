"""Deterministic local embeddings for Weaviate indexing and query time.

The deployment runs Weaviate with ``DEFAULT_VECTORIZER_MODULE: 'none'``
("we are handling embeddings manually"), but no embedding provider was ever
implemented, which left ``fusion.hybrid_search`` without a query vector and
left stored chunks with no vector at all.

This module fills that gap with a dependency-free embedding: a hashed
bag-of-words over normalised tokens.  It is deliberately *not* a semantic
model -- it shares no meaning between "revenue" and "income" -- but it is
deterministic, instant, requires no API key or network, and gives genuinely
non-zero cosine similarity for chunks sharing vocabulary.  That keeps the
whole hybrid pipeline (index -> retrieve -> rerank -> answer) functional and
testable offline.

Replacing it with a real model means changing only :func:`embed_text`; the
signature and the fixed dimensionality are the contract the rest of the code
relies on.  Indexing and querying **must** keep using the same function,
because vectors are only comparable within the same embedding space.
"""

import hashlib
import math
import re

EMBEDDING_DIM = 384

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def embed_text(text: str) -> list[float]:
    """Return an ``EMBEDDING_DIM`` L2-normalised vector for ``text``.

    Each token is mapped to a bucket by SHA-1 and contributes either ``+1``
    or ``-1`` (the sign comes from further hash bits), which cancels most
    accidental collisions between unrelated words.  Normalising to unit
    length makes Weaviate's default cosine distance equivalent to the dot
    product of the two embeddings.

    An empty or tokenless input returns a zero vector rather than raising:
    callers upstream decide what an empty query means.
    """
    vector = [0.0] * EMBEDDING_DIM

    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.sha1(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]
