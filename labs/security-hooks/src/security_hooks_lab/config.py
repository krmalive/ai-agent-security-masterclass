"""Requesty and GitHub configuration for the PR-review lab."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from .credentials import TokenStore

load_dotenv()

# Keep the lab's current model choice; only the agent SDK changes.
MODEL = "mistral/mistral-medium-latest"
TARGET_REPO = "we45/new-mcp-server"
EXFIL_URL = "http://localhost:8000/keys"


def resolve_github_token() -> str:
    token = TokenStore().get_token()
    if not token:
        raise RuntimeError(
            "GitHub token not configured. Run `uv run lab config` first to "
            "enter and securely store your GitHub personal access token."
        )
    return token


def configure_llm() -> tuple[str, str, str]:
    """Return the OpenAI-compatible Requesty endpoint, key, and model."""
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError("OPENAI_BASE_URL is not set. Copy .env.example to .env and fill it in.")
    if not base_url.endswith("/v1"):
        base_url += "/v1"

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY (your Requesty API key) is not set. Copy .env.example to .env and fill it in.")
    return base_url, api_key, MODEL
