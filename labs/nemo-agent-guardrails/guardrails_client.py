"""HTTP client for the NeMo Guardrails server running in Docker.

The server hosts two rail configurations (see guardrails/config/):

  intent_rails    — embeddings-based intent triage of every user message
  retrieval_rails — sanitizes retrieved KB chunks, then generates a
                    grounded answer from them

Both are called through the server's /v1/chat/completions endpoint with a
config_id selecting the rail set.
"""

import os
from dataclasses import dataclass, field

import httpx
from dotenv import load_dotenv

load_dotenv()

NEMO_URL = os.getenv("NEMO_GUARDRAILS_URL", "http://localhost:8001")

# Bot messages defined in intent_rails/rails.co. The sentinel means "message
# may proceed to the agent"; anything in REFUSALS is a block, returned to the
# user verbatim. Keep in sync with the Colang file.
ALLOWED_SENTINEL = "ALLOWED"
REFUSALS = {
    "I can't change how I operate or step outside my role as NovaBank's support assistant. I'm happy to help with your account, cards, or our policies.": "attempt jailbreak",
    "I can't share my internal instructions or configuration. If you have a question about NovaBank accounts, cards, or policies, I'm glad to help.": "probe system prompt",
    "I can only discuss the account you are authenticated for. I can't share information about any other customer.": "request other customer data",
    "I can't help with that. If you believe there's genuine fraud on your account, I can explain how to report it to our fraud team.": "request fraud assistance",
    "I'm NovaBank's support assistant, so I'll stick to banking topics. I can help with your account, cards, transfers, fees, and our policies.": "ask off topic",
}


@dataclass
class IntentResult:
    blocked: bool
    message: str          # refusal text when blocked, sentinel otherwise
    matched_intent: str | None = None
    activated_flows: list[str] = field(default_factory=list)


@dataclass
class GuardedRagResult:
    answer: str
    sanitized_chunks: str | None = None
    activated_flows: list[str] = field(default_factory=list)


class GuardrailsUnavailable(Exception):
    """The NeMo Guardrails container is not reachable."""


def _extract_reply(data: dict) -> str:
    # NeMo Guardrails >= 0.23 serves an OpenAI-compatible response shape.
    if data.get("choices"):
        return data["choices"][0].get("message", {}).get("content", "") or ""
    return ""


def _extract_flows(data: dict) -> list[str]:
    """Names of the rails/flows that ran, from guardrails.log.activated_rails."""
    log = (data.get("guardrails") or {}).get("log") or {}
    rails = log.get("activated_rails") or []
    flows = []
    for rail in rails:
        name = rail.get("name") if isinstance(rail, dict) else None
        if name:
            flows.append(name)
    return flows


async def _post(payload: dict, timeout: float = 60.0) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{NEMO_URL}/v1/chat/completions", json=payload
            )
            response.raise_for_status()
            return response.json()
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        raise GuardrailsUnavailable(
            f"Cannot reach the NeMo Guardrails server at {NEMO_URL}. "
            "Is the container running? Start it with: docker compose up -d"
        ) from exc


async def check_intent(message: str) -> IntentResult:
    """Run the user's message through the intent rails.

    No LLM is involved: the intent_rails config classifies the message by
    embedding similarity and answers with either a canned refusal or the
    ALLOWED sentinel.
    """
    data = await _post(
        {
            # `model` is required by the OpenAI-compatible schema; the rails
            # config decides what (if anything) actually gets called.
            "model": os.getenv("MODEL_NAME", "openai/gpt-5.6-luna"),
            "messages": [{"role": "user", "content": message}],
            "guardrails": {
                "config_id": "intent_rails",
                "options": {"log": {"activated_rails": True}},
            },
        }
    )
    reply = _extract_reply(data).strip()
    flows = _extract_flows(data)
    if reply in REFUSALS:
        return IntentResult(
            blocked=True,
            message=reply,
            matched_intent=REFUSALS[reply],
            activated_flows=flows,
        )
    # The sentinel (or anything unexpected) lets the message through — the
    # intent rails are a triage layer, not the only line of defense.
    return IntentResult(
        blocked=False,
        message=reply,
        matched_intent="allowed intent" if reply == ALLOWED_SENTINEL else None,
        activated_flows=flows,
    )


async def guarded_rag_answer(question: str, chunks_text: str) -> GuardedRagResult:
    """Send question + retrieved chunks through the retrieval rails.

    The chunks are passed as a `context` message; the retrieval rails
    (drop injected chunks, mask customer pii) rewrite $relevant_chunks
    before the LLM generates a grounded answer. `output_vars` returns the
    sanitized chunks so the UI can show before/after.
    """
    data = await _post(
        {
            "model": os.getenv("MODEL_NAME", "openai/gpt-5.6-luna"),
            "messages": [{"role": "user", "content": question}],
            "guardrails": {
                "config_id": "retrieval_rails",
                # The retrieved chunks enter the rails as context; retrieval
                # rails rewrite $relevant_chunks before generation sees it.
                "context": {"relevant_chunks": chunks_text},
                "options": {
                    "output_vars": ["relevant_chunks"],
                    "log": {"activated_rails": True},
                },
            },
        },
        timeout=120.0,
    )
    output_data = (data.get("guardrails") or {}).get("output_data") or {}
    return GuardedRagResult(
        answer=_extract_reply(data).strip(),
        sanitized_chunks=output_data.get("relevant_chunks"),
        activated_flows=_extract_flows(data),
    )


async def server_healthy() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{NEMO_URL}/v1/rails/configs")
            return response.status_code == 200
    except httpx.HTTPError:
        return False
