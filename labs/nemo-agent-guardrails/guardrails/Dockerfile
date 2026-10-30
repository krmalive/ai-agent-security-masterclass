# NeMo Guardrails server — hosts the intent_rails and retrieval_rails configs
# for the NovaBank agent. Built once by setup.sh; started by the student with
# `docker compose up -d`.
FROM python:3.12-slim

# annoy (NeMo's vector index) ships no wheels for every platform — needs a compiler
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "nemoguardrails[openai,server]==0.23.0" langchain-openai fastembed

# Pre-download the embedding model used for intent matching so the server
# starts instantly and works without internet access to HuggingFace.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='sentence-transformers/all-MiniLM-L6-v2')"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# The rail configs are mounted read-only at /config-src (see docker-compose.yml);
# the entrypoint renders them into /run-config so student edits on the host are
# picked up with a simple `docker compose restart`.
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
