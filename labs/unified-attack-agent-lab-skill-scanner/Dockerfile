FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY skills/ ./skills/
COPY data/ ./data/
COPY reports/ ./reports/

ENV PYTHONPATH=/app

EXPOSE 8080
CMD ["uv", "run", "--", "python", "-m", "backend.app"]
