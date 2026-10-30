"""Environment bootstrap for lab-style LLM variables.

This module allows local lab setups that already define OpenAI/Requesty
variables in a `.env` file to work with skill-scanner's SKILL_SCANNER_* names.
"""

from __future__ import annotations

import os
from typing import Final

from dotenv import load_dotenv

_BOOTSTRAPPED = False

_ENV_ALIAS_MAP: Final[dict[str, tuple[str, ...]]] = {
    "SKILL_SCANNER_LLM_API_KEY": ("OPENAI_API_KEY", "REQUESTY_API_KEY"),
    "SKILL_SCANNER_LLM_BASE_URL": ("OPENAI_API_BASE", "OPENAI_BASE_URL", "BASE_URL"),
    "SKILL_SCANNER_LLM_MODEL": ("LLM_MODEL",),
}


def _first_non_empty(env_names: tuple[str, ...]) -> str | None:
    for name in env_names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def _set_if_unset(target_name: str, value: str | None) -> None:
    if value and not os.getenv(target_name):
        os.environ[target_name] = value


def bootstrap_skill_scanner_llm_env() -> None:
    """Populate SKILL_SCANNER_* variables from common lab aliases.

    Rules:
    - Load dotenv once with ``override=False`` so exported shell vars win.
    - Never overwrite explicitly set SKILL_SCANNER_* variables.
    - Provide openai provider/model defaults for lab demos when unset.
    """

    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return

    load_dotenv(override=False)

    for target_name, aliases in _ENV_ALIAS_MAP.items():
        _set_if_unset(target_name, _first_non_empty(aliases))

    _set_if_unset("SKILL_SCANNER_LLM_PROVIDER", "openai")
    _set_if_unset("SKILL_SCANNER_LLM_MODEL", "gpt-4.1-mini")
    _set_if_unset("SKILL_SCANNER_META_LLM_API_KEY", os.getenv("SKILL_SCANNER_LLM_API_KEY"))

    _BOOTSTRAPPED = True
