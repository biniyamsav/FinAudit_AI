class ExtractionError(Exception):
    """Fatal extraction failure. ``code`` is stored on the ingestion job."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def clean_text(value: str | None) -> str:
    """JSON/JSONB rejects NUL bytes; strip them from every extracted string."""
    return (value or "").replace("\x00", "")
