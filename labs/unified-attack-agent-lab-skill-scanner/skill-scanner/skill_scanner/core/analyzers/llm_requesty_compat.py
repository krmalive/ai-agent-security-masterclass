# Copyright 2026 Cisco Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""Compatibility helpers for OpenAI-compatible routers with strict model IDs."""

from __future__ import annotations

from typing import Any


def _requesty_provider_model(model: str) -> str | None:
    """Return a Requesty-style ``provider/model`` id, or None if model is empty."""
    m = (model or "").strip()
    if not m:
        return None
    if "/" in m:
        return m
    lower = m.lower()
    # Common LiteLLM short names without a provider segment — Requesty rejects these.
    if lower.startswith(("gpt-", "chatgpt")) or lower.startswith(("o1", "o3", "o4")):
        return f"openai/{m}"
    if lower.startswith("claude"):
        return f"anthropic/{m}"
    if lower.startswith("gemini"):
        return f"google/{m}"
    # Lab default: OpenAI-compatible short ids
    return f"openai/{m}"


def apply_requesty_model_body_fix(params: dict[str, Any], *, model: str) -> dict[str, Any]:
    """Merge ``model`` into ``extra_body`` for Requesty when using LiteLLM.

    Requesty's router validates that chat-completion payloads use ``provider/model``.
    LiteLLM's OpenAI transport sometimes forwards only the bare model segment to
    custom ``api_base`` hosts, which triggers ``Invalid model, expected: provider/model``.
    Passing the full id via ``extra_body`` restores the value on the wire for many
    LiteLLM versions (merged into the outbound JSON body).
    """
    api_base = params.get("api_base")
    if not isinstance(api_base, str) or "requesty.ai" not in api_base.lower():
        return params
    full = _requesty_provider_model(model)
    if full is None:
        return params

    out = dict(params)
    extra: dict[str, Any] = dict(out.get("extra_body") or {})
    extra["model"] = full
    out["extra_body"] = extra
    # Align top-level model so LiteLLM routing matches Requesty's expected id.
    out["model"] = full
    return out
