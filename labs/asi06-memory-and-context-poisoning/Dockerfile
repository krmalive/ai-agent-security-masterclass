FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml ./
COPY uv.lock* ./

RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f uv.lock ]; then uv sync --frozen; else uv sync; fi

COPY scripts/fetch_embedding_model.py ./scripts/
RUN uv run python scripts/fetch_embedding_model.py

COPY backend/ ./backend/
COPY frontend/ ./frontend/

ENV PYTHONPATH=/app
ENV CHROMA_DB_PATH=/app/data/chroma_db
ENV CHROMA_EMBEDDING_MODEL_PATH=/app/models/all-MiniLM-L6-v2

EXPOSE 8080

CMD ["uv", "run", "flask", "run", "--host", "0.0.0.0", "--port", "8080"]
