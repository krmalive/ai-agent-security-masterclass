"""Schema-validation defense layer against MCP tool poisoning.

The insecure client trusts whatever an MCP server advertises. This module wraps the
OpenAI-Agents MCP client so that, before any tool reaches the LLM or gets invoked, it is
run through schema-based checks. Wrap the *untrusted* (third-party) server with these;
trusted first-party servers can stay as-is.

1. Description sanitisation — a tool description must be plain text: no hidden-instruction
   markup (``<IMPORTANT>``, ``<HIDDEN>``, ``<SYSTEM>`` ...), no imperative directives
   ("you must", "do not disclose", "copy ... verbatim"), bounded length. Non-conforming
   content is stripped before the model ever sees it, so the poisoning can't steer it.

2. Argument validation — every tool call is validated against a strict JSON Schema
   (``additionalProperties: false``, length caps) AND scanned for sensitive data leaving
   the environment (egress DLP): SSNs and internal-record markers in the arguments are
   blocked. So even if the model were induced to gather secrets, it can't smuggle them out
   through a tool argument.

The wrappers subclass the SDK's MCP client classes, so they are drop-in replacements for
``MCPServerStdio`` / ``MCPServerSse``.
"""

from __future__ import annotations

import re
from typing import Any

from jsonschema import Draft202012Validator
from mcp.types import CallToolResult, TextContent, Tool as MCPTool

from agents.mcp import MCPServerSse, MCPServerStdio

# --- Policy 1: description content policy ------------------------------------------

_FORBIDDEN_TAG_BLOCKS = re.compile(
    r"<\s*(important|hidden|system|secret|instructions?)\s*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_STRAY_TAGS = re.compile(r"</?\s*(important|hidden|system|secret|instructions?)\s*>", re.IGNORECASE)
_DIRECTIVE_LINE = re.compile(
    r"(?im)^.*\b(you must|do not (mention|disclose|tell|reveal|summar)|silently|verbatim|"
    r"copy (its|the) (entire|full)|without (telling|informing)|present it as|"
    r"before (calling|submitting|using))\b.*$"
)
_MAX_DESC_LEN = 400


def sanitize_description(name: str, description: str | None) -> tuple[str, list[str]]:
    """Return (clean_description, findings). ``findings`` is non-empty when poisoning was removed."""
    original = description or ""
    findings: list[str] = []

    cleaned = original
    if _FORBIDDEN_TAG_BLOCKS.search(cleaned):
        findings.append(f"{name}: hidden instruction block (<IMPORTANT>/<HIDDEN>/...) stripped")
        cleaned = _FORBIDDEN_TAG_BLOCKS.sub(" ", cleaned)
    if _STRAY_TAGS.search(cleaned):
        cleaned = _STRAY_TAGS.sub(" ", cleaned)
    if _DIRECTIVE_LINE.search(cleaned):
        findings.append(f"{name}: imperative directive line(s) stripped")
        cleaned = _DIRECTIVE_LINE.sub(" ", cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > _MAX_DESC_LEN:
        findings.append(f"{name}: description truncated to {_MAX_DESC_LEN} chars")
        cleaned = cleaned[:_MAX_DESC_LEN].rstrip()

    return cleaned, findings


# --- Policy 2: per-tool argument schemas + egress DLP ------------------------------

# Strict schema for each untrusted tool. additionalProperties:false rejects smuggled args;
# length caps bound the payload. Unknown tools fall back to a permissive schema.
_ARG_SCHEMAS: dict[str, dict[str, Any]] = {
    "submit_support_ticket": {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "maxLength": 300},
            "context": {"type": "string", "maxLength": 500},
        },
        "required": ["summary"],
        "additionalProperties": False,
    },
}

# Egress DLP: sensitive data that must never leave via a tool argument.
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_SENSITIVE_MARKERS = ["employee directory", "ssn", "salary"]


def _egress_violation(arguments: dict[str, Any]) -> str | None:
    blob = " ".join(str(v) for v in arguments.values())
    if _SSN_RE.search(blob):
        return "sensitive data (SSN pattern) detected in tool arguments"
    low = blob.lower()
    for marker in _SENSITIVE_MARKERS:
        if marker in low:
            return f"sensitive internal data ({marker!r}) detected in tool arguments"
    return None


def validate_arguments(tool_name: str, arguments: dict[str, Any] | None) -> str | None:
    """Return an error string if the call violates policy, else ``None``."""
    args = arguments or {}
    schema = _ARG_SCHEMAS.get(tool_name)
    if schema is not None:
        errors = sorted(Draft202012Validator(schema).iter_errors(args), key=str)
        if errors:
            return f"argument schema violation: {errors[0].message}"
    return _egress_violation(args)


# --- The guarded MCP client wrappers ----------------------------------------------

class _SchemaGuardMixin:
    """Mixin that hardens ``list_tools`` and ``call_tool`` on an MCP client class."""

    async def list_tools(self, *args: Any, **kwargs: Any) -> list[MCPTool]:
        tools = await super().list_tools(*args, **kwargs)
        for tool in tools:
            clean, findings = sanitize_description(tool.name, tool.description)
            if findings:
                print(f"[schema-guard] {'; '.join(findings)}")
            tool.description = clean
            if tool.name in _ARG_SCHEMAS:
                tool.inputSchema = _ARG_SCHEMAS[tool.name]
        return tools

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None, *args: Any, **kwargs: Any
    ) -> CallToolResult:
        error = validate_arguments(tool_name, arguments)
        if error is not None:
            print(f"[schema-guard] BLOCKED {tool_name}: {error}")
            return CallToolResult(
                isError=True,
                content=[TextContent(type="text", text=f"[BLOCKED by schema validation] {error}")],
            )
        return await super().call_tool(tool_name, arguments, *args, **kwargs)


class SchemaValidatingMCPServerStdio(_SchemaGuardMixin, MCPServerStdio):
    """``MCPServerStdio`` with the tool-poisoning defense layer applied."""


class SchemaValidatingMCPServerSse(_SchemaGuardMixin, MCPServerSse):
    """``MCPServerSse`` with the tool-poisoning defense layer applied."""
