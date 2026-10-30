from __future__ import annotations

from skill_scanner.core import llm_lab_env
from skill_scanner.core.llm_lab_env import bootstrap_skill_scanner_llm_env


def _reset_bootstrap_state() -> None:
    llm_lab_env._BOOTSTRAPPED = False


def test_bootstrap_maps_lab_aliases_when_scanner_vars_absent(monkeypatch):
    _reset_bootstrap_state()
    monkeypatch.delenv("SKILL_SCANNER_LLM_API_KEY", raising=False)
    monkeypatch.delenv("SKILL_SCANNER_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("SKILL_SCANNER_LLM_MODEL", raising=False)
    monkeypatch.delenv("SKILL_SCANNER_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("SKILL_SCANNER_META_LLM_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "lab-key")
    monkeypatch.setenv("OPENAI_API_BASE", "https://router.requesty.ai/v1")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4.1-mini")

    bootstrap_skill_scanner_llm_env()

    assert llm_lab_env.os.getenv("SKILL_SCANNER_LLM_API_KEY") == "lab-key"
    assert llm_lab_env.os.getenv("SKILL_SCANNER_LLM_BASE_URL") == "https://router.requesty.ai/v1"
    assert llm_lab_env.os.getenv("SKILL_SCANNER_LLM_MODEL") == "openai/gpt-4.1-mini"
    assert llm_lab_env.os.getenv("SKILL_SCANNER_LLM_PROVIDER") == "openai"
    assert llm_lab_env.os.getenv("SKILL_SCANNER_META_LLM_API_KEY") == "lab-key"


def test_bootstrap_does_not_override_explicit_scanner_vars(monkeypatch):
    _reset_bootstrap_state()
    monkeypatch.setenv("SKILL_SCANNER_LLM_API_KEY", "scanner-key")
    monkeypatch.setenv("SKILL_SCANNER_LLM_BASE_URL", "https://scanner.example/v1")
    monkeypatch.setenv("SKILL_SCANNER_LLM_MODEL", "scanner-model")
    monkeypatch.setenv("SKILL_SCANNER_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SKILL_SCANNER_META_LLM_API_KEY", "scanner-meta-key")
    monkeypatch.setenv("OPENAI_API_KEY", "lab-key")
    monkeypatch.setenv("OPENAI_API_BASE", "https://router.requesty.ai/v1")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4.1-mini")

    bootstrap_skill_scanner_llm_env()

    assert llm_lab_env.os.getenv("SKILL_SCANNER_LLM_API_KEY") == "scanner-key"
    assert llm_lab_env.os.getenv("SKILL_SCANNER_LLM_BASE_URL") == "https://scanner.example/v1"
    assert llm_lab_env.os.getenv("SKILL_SCANNER_LLM_MODEL") == "scanner-model"
    assert llm_lab_env.os.getenv("SKILL_SCANNER_LLM_PROVIDER") == "anthropic"
    assert llm_lab_env.os.getenv("SKILL_SCANNER_META_LLM_API_KEY") == "scanner-meta-key"


def test_bootstrap_uses_requesty_key_and_defaults(monkeypatch):
    _reset_bootstrap_state()
    monkeypatch.delenv("SKILL_SCANNER_LLM_API_KEY", raising=False)
    monkeypatch.delenv("SKILL_SCANNER_LLM_MODEL", raising=False)
    monkeypatch.delenv("SKILL_SCANNER_META_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("REQUESTY_API_KEY", "requesty-key")

    bootstrap_skill_scanner_llm_env()

    assert llm_lab_env.os.getenv("SKILL_SCANNER_LLM_API_KEY") == "requesty-key"
    assert llm_lab_env.os.getenv("SKILL_SCANNER_LLM_MODEL") == "gpt-4.1-mini"
    assert llm_lab_env.os.getenv("SKILL_SCANNER_META_LLM_API_KEY") == "requesty-key"
