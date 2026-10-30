"""Bundled Chroma embedding model — avoids runtime HuggingFace/S3 downloads."""

from __future__ import annotations

import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from backend.config import Config

try:
    from chromadb.utils.embedding_functions.onnx_mini_lm_l6_v2 import ONNXMiniLM_L6_V2

    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False


class BundledONNXMiniLM_L6_V2(ONNXMiniLM_L6_V2 if _AVAILABLE else object):  # type: ignore[misc]
    """ONNX MiniLM that reads from the lab's bundled models/ directory."""

    MODEL_NAME = "all-MiniLM-L6-v2"
    DOWNLOAD_PATH = Path(Config.CHROMA_EMBEDDING_MODEL_PATH)

    @staticmethod
    def name() -> str:
        # Match Chroma's persisted collection config for the default ONNX embedder.
        return "default"


def _ensure_bundled_model() -> None:
    onnx_model = Path(Config.CHROMA_EMBEDDING_MODEL_PATH) / "onnx" / "model.onnx"
    if onnx_model.is_file():
        return
    script = Path(__file__).resolve().parents[2] / "scripts" / "fetch_embedding_model.py"
    if not script.is_file():
        raise FileNotFoundError(
            f"Bundled embedding model missing at {onnx_model} and fetch script not found."
        )
    subprocess.run([sys.executable, str(script)], check=True)


@lru_cache(maxsize=1)
def get_embedding_function():
    """Return a warmed-up embedding function backed by the bundled ONNX model."""
    if not _AVAILABLE:
        return None
    _ensure_bundled_model()
    embedding_fn = BundledONNXMiniLM_L6_V2()
    embedding_fn(["warmup"])
    return embedding_fn
