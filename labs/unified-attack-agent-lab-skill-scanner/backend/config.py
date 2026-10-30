import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4.1-mini")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://router.requesty.ai/v1")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    SECRET_KEY = os.getenv("SECRET_KEY", "attack-lab-dev-only")

    UPLOAD_FOLDER = "/app/data/uploads"
    EXPORT_FOLDER = "/app/data/exports"
    SESSION_PROFILE_PATH = "/app/data/session_context.json"
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
