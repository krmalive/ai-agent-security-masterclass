#!/usr/bin/env python3
"""Download and extract the Chroma all-MiniLM-L6-v2 ONNX bundle into models/."""

from __future__ import annotations

import hashlib
import os
import sys
import tarfile
import urllib.request
from pathlib import Path

MODEL_NAME = "all-MiniLM-L6-v2"
MODEL_URL = (
    "https://chroma-onnx-models.s3.amazonaws.com/all-MiniLM-L6-v2/onnx.tar.gz"
)
MODEL_SHA256 = "913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3"
ONNX_FILES = (
    "config.json",
    "model.onnx",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "vocab.txt",
)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _model_root() -> Path:
    env = os.getenv("CHROMA_EMBEDDING_MODEL_PATH")
    if env:
        return Path(env)
    return _project_root() / "models" / MODEL_NAME


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4096), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _onnx_ready(root: Path) -> bool:
    onnx_dir = root / "onnx"
    return all((onnx_dir / name).is_file() for name in ONNX_FILES)


def fetch_model(*, force: bool = False) -> Path:
    root = _model_root()
    if not force and _onnx_ready(root):
        print(f"Embedding model already present at {root / 'onnx'}")
        return root

    root.mkdir(parents=True, exist_ok=True)
    archive = root / "onnx.tar.gz"
    if not archive.is_file() or _sha256(archive) != MODEL_SHA256:
        print(f"Downloading {MODEL_NAME} ONNX bundle...")
        with urllib.request.urlopen(MODEL_URL, timeout=120) as response:
            archive.write_bytes(response.read())
        if _sha256(archive) != MODEL_SHA256:
            archive.unlink(missing_ok=True)
            raise RuntimeError("Downloaded ONNX archive failed SHA256 verification.")

    print(f"Extracting {archive.name} to {root}...")
    with tarfile.open(archive, "r:gz") as tar:
        if sys.version_info >= (3, 12):
            tar.extractall(path=root, filter="data")
        else:
            tar.extractall(path=root)

    if not _onnx_ready(root):
        raise RuntimeError(f"Extracted model is incomplete under {root / 'onnx'}")

    print(f"Ready: {root / 'onnx'}")
    return root


if __name__ == "__main__":
    fetch_model(force="--force" in sys.argv)
