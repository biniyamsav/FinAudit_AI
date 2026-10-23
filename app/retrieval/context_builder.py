import ast
import json
from typing import Any, Dict, List

EMPTY_CONTEXT_MESSAGE = "No relevant financial records found in workspace"

# Ordered metadata keys -> human labels, so the citation header stays stable
# as more provenance fields are added by the chunker.
_PROVENANCE_LABELS = (
    ("page", "Page"),
    ("table_index", "Table"),
    ("sheet", "Sheet"),
    ("row", "Row"),
    ("cell", "Cell"),
)


def _coerce_provenance(raw: Any) -> Dict[str, Any]:
    """Return provenance as a dict whatever shape it arrives in.

    The two live paths disagree on representation: the in-process chunker
    (``app.ingestion.chunking``) produces a real ``dict``, while
    ``dense.store_chunks_in_weaviate`` persists ``str(chunk.provenance)``,
    so Weaviate hands it back as a repr-style string such as
    ``"{'source_type': 'pdf', 'page': 3}"``.  Try JSON, then a Python
    literal, then give up quietly -- a citation header is worth losing, an
    audit retrieval call is not.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(text)
            except (ValueError, SyntaxError):
                continue
            if isinstance(parsed, dict):
                return parsed
    return {}


def _provenance_header(
    index: int, chunk: Dict[str, Any], provenance: Dict[str, Any]
) -> str:
    """Build the Markdown header that makes a chunk citable.

    Evidence provenance is an invariant of this platform: every financial
    fact handed to the model must be traceable to an exact file and, where
    the source has one, an exact page / table / sheet.  Only fields that are
    actually present are emitted, so a CSV chunk does not grow a fake
    "Page: None" line.
    """
    document_id = chunk.get("document_id") or provenance.get("document_id")
    lines = [f"### Source {index}"]
    if document_id:
        lines.append(f"**Document ID:** `{document_id}`")

    details: List[str] = []
    source_type = provenance.get("source_type") or chunk.get("file_type")
    if source_type:
        details.append(str(source_type))
    for key, label in _PROVENANCE_LABELS:
        value = provenance.get(key)
        if value is not None and value != "":
            details.append(f"{label} {value}")

    if details:
        # ASCII separator on purpose: this header is logged and piped into
        # prompts on Windows consoles, where a non-ASCII separator mojibakes.
        lines.append("**From:** " + " | ".join(details))
    return "\n".join(lines)


def build_rag_context(chunks: List[Dict[str, Any]]) -> str:
    """Assemble reranked chunks into a Markdown context block for an LLM prompt.

    Each chunk is rendered as a Markdown section: a provenance header
    (Document ID plus whichever of Page / Table / Sheet the source carries)
    followed by the extracted text, with ``---`` between sections.  That
    structure is what lets the model answer an audit question by citing a
    specific page of a specific file, and lets a reviewer check the cite.

    An empty result set is reported explicitly rather than rendered as an
    empty string, so the prompt cannot silently read as "the model found
    nothing" when the truth is "retrieval returned nothing".
    """
    if not chunks:
        return EMPTY_CONTEXT_MESSAGE

    sections: List[str] = []
    for index, chunk in enumerate(chunks, start=1):
        provenance = _coerce_provenance(chunk.get("provenance"))
        header = _provenance_header(index, chunk, provenance)
        text = (chunk.get("text") or "").strip()
        sections.append(f"{header}\n\n{text or '(no text extracted)'}")

    return "\n\n---\n\n".join(sections)
