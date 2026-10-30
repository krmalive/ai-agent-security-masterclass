# Copyright 2026 Cisco Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0

"""Tests for Requesty + LiteLLM compatibility shim."""

from skill_scanner.core.analyzers.llm_requesty_compat import apply_requesty_model_body_fix


def test_requesty_fix_adds_extra_body_model():
    params = {
        "model": "openai/gpt-4.1-mini",
        "api_base": "https://router.requesty.ai/v1",
        "messages": [],
    }
    out = apply_requesty_model_body_fix(params, model="openai/gpt-4.1-mini")
    assert out["extra_body"]["model"] == "openai/gpt-4.1-mini"


def test_non_requesty_base_unchanged():
    params = {"model": "gpt-4o", "api_base": "https://api.openai.com/v1"}
    out = apply_requesty_model_body_fix(params, model="gpt-4o")
    assert out == params


def test_requesty_fix_prefixes_bare_openai_model():
    params = {
        "model": "gpt-4.1-mini",
        "api_base": "https://router.requesty.ai/v1",
        "messages": [],
    }
    out = apply_requesty_model_body_fix(params, model="gpt-4.1-mini")
    assert out["extra_body"]["model"] == "openai/gpt-4.1-mini"
    assert out["model"] == "openai/gpt-4.1-mini"
