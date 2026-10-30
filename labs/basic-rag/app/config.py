from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CHROMA_PATH = Path(
    os.getenv("CHROMA_PATH", str(ROOT_DIR / ".data" / "chroma"))
).resolve()

# CrewAI's supported Chroma configuration derives its persistent directory from
# CREWAI_STORAGE_DIR. Set it before CrewAI is imported so we can avoid passing
# Chroma's Pydantic-v1 Settings object through Pydantic 2 validation.
os.environ.setdefault("CREWAI_STORAGE_DIR", str(DEFAULT_CHROMA_PATH))


def requesty_model(model: str) -> str:
    """Return Requesty's required provider/model identifier."""
    model = model.strip()
    return model if "/" in model else f"openai/{model}"


@dataclass(frozen=True)
class Settings:
    requesty_api_key: str = os.getenv("REQUESTY_API_KEY", "")
    requesty_base_url: str = os.getenv(
        "REQUESTY_BASE_URL", "https://router.requesty.ai/v1"
    ).rstrip("/")
    chat_model: str = requesty_model(
        os.getenv("CHAT_MODEL", "openai/gpt-5.6-luna")
    )
    embedding_model: str = requesty_model(
        os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
    )
    wstg_pdf_path: Path = Path(
        os.getenv("WSTG_PDF_PATH", str(ROOT_DIR / "data" / "wstg-v4.2.pdf"))
    ).resolve()
    shopfast_path: Path = Path(
        os.getenv("SHOPFAST_PATH", str(ROOT_DIR / "shopfast"))
    ).resolve()
    chroma_path: Path = DEFAULT_CHROMA_PATH
    max_output_tokens: int = int(os.getenv("MAX_OUTPUT_TOKENS", "16000"))

    @property
    def configured(self) -> bool:
        return bool(self.requesty_api_key and self.wstg_pdf_path.exists())

    def readiness_errors(self) -> list[str]:
        errors: list[str] = []
        if not self.requesty_api_key:
            errors.append("REQUESTY_API_KEY is not set")
        if not self.wstg_pdf_path.exists():
            errors.append(f"WSTG PDF not found: {self.wstg_pdf_path}")
        if not self.shopfast_path.exists():
            errors.append(f"ShopFast fixture not found: {self.shopfast_path}")
        return errors


settings = Settings()
