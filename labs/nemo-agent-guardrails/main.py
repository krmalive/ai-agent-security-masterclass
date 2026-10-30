"""NovaBank support chat — FastAPI app orchestrating the guardrails and agent.

Request flow for every chat message:

  1. INTENT RAILS (optional) — the message is sent to the NeMo Guardrails
     container (config: intent_rails). Blocked intents return a canned
     refusal and the agent never runs.
  2. AGENT — the OpenAI Agents SDK agent handles the message with its tools.
  3. RETRIEVAL RAILS (optional) — inside the search_knowledge_base tool,
     retrieved chunks are sanitized by the NeMo retrieval rails before
     answer generation.

Both rail layers can be toggled per-message from the UI so students can
contrast guarded and unguarded behavior.
"""

import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import retrieval
from agent import LabContext, run_agent
from guardrails_client import GuardrailsUnavailable, check_intent, server_healthy

load_dotenv()

app = FastAPI(title="NovaBank Support — NeMo Guardrails Lab")
templates = Jinja2Templates(directory="templates")

# In-memory chat sessions: session_id -> agent input history
SESSIONS: dict[str, list] = {}

# Documents that are intentionally tainted, flagged on the /kb page
KB_FLAGS = {
    "premium-refunds.md": ("poisoned", "Contains an indirect prompt-injection payload"),
    "customer-escalations.md": ("pii", "Contains customer PII (test data)"),
}


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    intent_rails: bool = True
    retrieval_rails: bool = True


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/kb", response_class=HTMLResponse)
async def knowledge_base(request: Request):
    docs = []
    for name, content in retrieval.load_documents().items():
        flag, note = KB_FLAGS.get(name, (None, None))
        docs.append({"name": name, "content": content, "flag": flag, "note": note})
    return templates.TemplateResponse(request, "kb.html", {"docs": docs})


@app.get("/api/health")
async def health():
    return {
        "nemo_guardrails": await server_healthy(),
        "llm_key_present": bool(os.getenv("REQUESTY_API_KEY")),
    }


@app.post("/api/reset")
async def reset(body: dict):
    SESSIONS.pop(body.get("session_id", ""), None)
    return {"ok": True}


@app.post("/api/chat")
async def chat(body: ChatRequest):
    session_id = body.session_id or str(uuid.uuid4())
    history = SESSIONS.get(session_id, [])
    ctx = LabContext(retrieval_rails_on=body.retrieval_rails)

    # ------------------------------------------------------------------
    # Layer 1: intent rails (NeMo Guardrails, embeddings-only dialog rails)
    # ------------------------------------------------------------------
    if body.intent_rails:
        try:
            intent = await check_intent(body.message)
        except GuardrailsUnavailable as exc:
            return JSONResponse(status_code=502, content={"error": str(exc)})
        if intent.blocked:
            ctx.add(
                "intent",
                "Intent rails: BLOCKED",
                f"Matched blocked intent: \"{intent.matched_intent}\". "
                "The agent was never invoked.",
            )
            # Keep the conversation coherent for the next turn
            history = history + [
                {"role": "user", "content": body.message},
                {"role": "assistant", "content": intent.message},
            ]
            SESSIONS[session_id] = history
            return {
                "session_id": session_id,
                "reply": intent.message,
                "blocked": True,
                "trace": ctx.trace,
            }
        ctx.add(
            "intent",
            "Intent rails: allowed",
            "Message classified as a legitimate banking intent — forwarded "
            "to the agent.",
        )
    else:
        ctx.add(
            "intent",
            "Intent rails OFF",
            "Message sent straight to the agent with no triage.",
        )

    # ------------------------------------------------------------------
    # Layer 2: the agent (OpenAI Agents SDK). Retrieval rails apply inside
    # the search_knowledge_base tool when enabled.
    # ------------------------------------------------------------------
    try:
        reply, new_history = await run_agent(
            history + [{"role": "user", "content": body.message}], ctx
        )
    except GuardrailsUnavailable as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})
    except RuntimeError as exc:
        # Typically: REQUESTY_API_KEY missing
        return JSONResponse(status_code=500, content={"error": str(exc)})
    except Exception as exc:  # surface LLM/API errors legibly for students
        return JSONResponse(
            status_code=500,
            content={"error": f"Agent error: {type(exc).__name__}: {exc}"},
        )

    SESSIONS[session_id] = new_history
    return {
        "session_id": session_id,
        "reply": str(reply),
        "blocked": False,
        "trace": ctx.trace,
    }
