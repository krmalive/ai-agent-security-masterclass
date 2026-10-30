"""Secure local storage for the GitHub PAT.

The token is taken from the user via `lab config` (hidden prompt) and stored in
~/.security-hooks-lab/config.json with owner-only (0600) permissions, instead of
living in an environment variable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx


class TokenStore:
    """Manages the locally stored GitHub token."""

    CONFIG_DIR = Path.home() / ".security-hooks-lab"
    CONFIG_FILE = CONFIG_DIR / "config.json"

    def __init__(self) -> None:
        self.config_dir = self.CONFIG_DIR
        self.config_file = self.CONFIG_FILE
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self.config_file.exists():
            return {}
        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: dict) -> None:
        with open(self.config_file, "w") as f:
            json.dump(data, f, indent=2)
        os.chmod(self.config_file, 0o600)

    def save_token(self, token: str) -> None:
        data = self._load()
        data["github_token"] = token
        self._save(data)

    def get_token(self) -> str | None:
        return self._load().get("github_token")

    def is_configured(self) -> bool:
        return bool(self.get_token())


def validate_github_token(token: str) -> tuple[bool, str | None]:
    """Validate a GitHub token by calling the API. Returns (ok, login)."""
    try:
        resp = httpx.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=10.0,
        )
    except httpx.HTTPError:
        return False, None
    if resp.status_code == 200:
        return True, resp.json().get("login")
    return False, None
