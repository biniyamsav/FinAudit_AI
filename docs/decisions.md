# Decisions

- SQLAlchemy pinned below 2.1: compiled extension blocked by Windows Application Control. Consequence: stay on 2.0.
- No durable original storage: originals stored in temp files and deleted after extraction. Consequence: re-extraction requires re-upload.
- No pgvector: vectors go to Weaviate. Consequence: two data stores.
- Money as strings: avoids float errors. Consequence: calculations need Decimal module.
- Alembic with hand-written initial migration. Consequence: schema changes tracked.
- OCR via rapidocr-onnxruntime. Consequence: local OCR without external service.