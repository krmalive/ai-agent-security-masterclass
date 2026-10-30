"""Custom retrieval-rail actions for the NovaBank knowledge base.

Both actions receive the guardrails context, read the `relevant_chunks`
string, and return a rewritten version of it. NeMo Guardrails assigns the
return value back to $relevant_chunks (see rails.co), so whatever these
functions return is what the LLM sees as context.

The web app joins retrieved chunks with CHUNK_SEPARATOR — keep this constant
in sync with retrieval.py on the app side.
"""

import re

from nemoguardrails.actions import action

CHUNK_SEPARATOR = "\n\n=====\n\n"

# Phrases that mark a document as carrying an indirect prompt-injection
# payload. Real deployments use classifiers for this; a pattern list keeps
# the mechanism legible for the lab (and is genuinely how many production
# filters start out).
INJECTION_PATTERNS = [
    r"ignore\s+(all|any|your|previous|prior)\s+.{0,30}instructions",
    r"disregard\s+.{0,30}(instructions|guidelines|rules)",
    r"system\s+(note|override|message)\s+to\s+(the\s+)?(ai|assistant|agent)",
    r"you\s+must\s+now\b",
    r"new\s+instructions\s*:",
    r"do\s+not\s+(tell|reveal|mention)\s+.{0,30}(user|customer)",
    r"reveal\s+.{0,30}(password|secret|credential)",
    r"\bAI\s+ASSISTANT\s*:",
]

PII_PATTERNS = [
    # US Social Security Numbers: 078-05-1120 -> ***-**-****
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "***-**-****"),
    # 16-digit card numbers with optional separators: 4111 1111 1111 1111
    (re.compile(r"\b(?:\d[ -]?){15}\d\b"), "****-****-****-****"),
    # NovaBank internal account numbers: NB-48291733
    (re.compile(r"\bNB-\d{8}\b"), "NB-********"),
    # Email addresses
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "<email masked>"),
    # US-style phone numbers: (415) 555-0173 / 415-555-0173
    (re.compile(r"\(?\b\d{3}\)?[ -.]\d{3}[-.]\d{4}\b"), "<phone masked>"),
]


def drop_injected_chunks(chunks_text: str) -> str:
    """Step 1 — remove whole chunks that contain prompt-injection payloads."""
    kept = []
    for chunk in chunks_text.split(CHUNK_SEPARATOR):
        lowered = chunk.lower()
        if any(re.search(p, lowered, re.IGNORECASE) for p in INJECTION_PATTERNS):
            # Replace the poisoned chunk with an audit marker instead of
            # silently vanishing it — the model (and the student) can see
            # that something was removed.
            kept.append(
                "[A retrieved document was removed by the retrieval rails: "
                "it contained instructions directed at the AI assistant.]"
            )
        else:
            kept.append(chunk)
    return CHUNK_SEPARATOR.join(kept)


def mask_customer_pii(chunks_text: str) -> str:
    """Step 2 — mask PII so the LLM (and its logs) never see real values."""
    for pattern, replacement in PII_PATTERNS:
        chunks_text = pattern.sub(replacement, chunks_text)
    return chunks_text


@action(name="sanitize_retrieved_chunks")
async def sanitize_retrieved_chunks(context: dict | None = None) -> str:
    """The retrieval rail: drop injected chunks, then mask PII.

    Both steps run inside ONE action on purpose. NeMo echoes every action's
    return value into the generation prompt's event history, so if these were
    two separate rails, the intermediate (half-sanitized) result of the first
    would still reach the LLM. A single action means the only value the LLM
    can ever see is the fully sanitized one.
    """
    chunks_text = (context or {}).get("relevant_chunks", "") or ""
    return mask_customer_pii(drop_injected_chunks(chunks_text))
