import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    LLM_MODEL = os.getenv('LLM_MODEL', 'openai/gpt-5.6-luna')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://router.requesty.ai/v1')

    MODE = os.getenv('MODE', 'attack')  # 'attack' or 'defense'
    MEMORY_SEAL_KEY = os.getenv('MEMORY_SEAL_KEY', 'asi06-demo-memory-seal-key')

    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    _BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _PROJECT = os.path.dirname(_BASE)
    CHROMA_DB_PATH = os.getenv('CHROMA_DB_PATH', os.path.join(_BASE, 'data', 'chroma_db'))
    CHROMA_EMBEDDING_MODEL_PATH = os.getenv(
        'CHROMA_EMBEDDING_MODEL_PATH',
        os.path.join(_PROJECT, 'models', 'all-MiniLM-L6-v2'),
    )
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
