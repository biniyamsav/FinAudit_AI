from typing import Any, Dict, List, Optional, Tuple


def _numeric(value: Any) -> Optional[float]:
    """Return ``value`` if it is a real number, otherwise ``None``.

    Metadata fields arrive as ``None`` when the query path did not request
    them, so every accessor has to tolerate a missing value.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _relevance(
    chunk: Dict[str, Any], score_low: Optional[float], score_high: Optional[float]
) -> float:
    """Map one chunk onto a comparable ``relevance`` value in ``[0, 1]``.

    The three query paths report "goodness" in two incompatible ways:

    * ``score`` (BM25 / hybrid) is unbounded and **higher is better**.
    * ``distance`` (dense near-vector) is a distance and **lower is better**.

    Sorting the raw numbers together would rank a dense distance of ``0.1``
    above a BM25 score of ``12.0``.  Scores are therefore min-max normalised
    across the batch; distances are mapped through ``1 / (1 + d)``, which is
    monotonically decreasing in ``d`` (so two dense hits keep their relative
    order) and always lands inside ``(0, 1]``.  A chunk carrying both
    prefers ``score``, which is the fused relevance the query asked for.
    """
    score = _numeric(chunk.get("score"))
    if score is not None:
        if score_high is None or score_low is None or score_high == score_low:
            return 1.0
        return (score - score_low) / (score_high - score_low)

    distance = _numeric(chunk.get("distance"))
    if distance is not None:
        return 1.0 / (1.0 + max(distance, 0.0))

    return 0.0


def _dedupe_key(chunk: Dict[str, Any]) -> Any:
    """Identity used to collapse duplicate retrievals.

    ``chunk_id`` is the authoritative key, but a chunk that lost its id in
    transit still has to be collapsed, so fall back to the
    ``(document_id, text)`` pair that identifies the same span of the same
    file.
    """
    chunk_id = chunk.get("chunk_id")
    if chunk_id is not None:
        return chunk_id
    return (chunk.get("document_id"), chunk.get("text"))


def rerank_chunks(
    chunks: List[Dict[str, Any]], top_k: int = 5
) -> List[Dict[str, Any]]:
    """Sort, normalise and de-duplicate retrieved chunks by relevance.

    Results arrive from ``sparse``, ``dense`` and ``fusion``, so they mix
    ``score`` and ``distance`` fields and may repeat the same chunk when the
    keyword and vector paths both hit it.  This converts every chunk to a
    shared ``relevance`` scale, drops duplicates (first occurrence wins,
    which preserves the original retrieval order across ties) and returns at
    most ``top_k`` items.

    Input dicts are never mutated; each returned chunk is a copy carrying an
    extra ``relevance`` field for the context builder and for logging.
    """
    if not chunks or top_k <= 0:
        return []

    scores = [
        value
        for value in (_numeric(chunk.get("score")) for chunk in chunks)
        if value is not None
    ]
    score_low = min(scores) if scores else None
    score_high = max(scores) if scores else None

    # Negating the position makes "later in the input" sort first among
    # equal relevance values, then the whole tuple is reversed.
    scored: List[Tuple[float, int, Dict[str, Any]]] = [
        (_relevance(chunk, score_low, score_high), -position, chunk)
        for position, chunk in enumerate(chunks)
    ]
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)

    seen = set()
    ranked: List[Dict[str, Any]] = []
    for relevance, _negated_position, chunk in scored:
        key = _dedupe_key(chunk)
        if key in seen:
            continue
        seen.add(key)
        enriched = dict(chunk)
        enriched["relevance"] = round(relevance, 6)
        ranked.append(enriched)
        if len(ranked) >= top_k:
            break

    return ranked
