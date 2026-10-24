FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
COPY ui ./ui
RUN useradd -m appuser && mkdir -p /data/uploads && chown -R appuser:appuser /data/uploads
USER appuser
ENV TEMP_UPLOAD_DIR=/data/uploads
EXPOSE 8000
COPY start.sh /app/start.sh
CMD ["sh", "/app/start.sh"]