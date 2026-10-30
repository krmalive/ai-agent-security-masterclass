"""Web UI for the brokered-credentials lab: agent chat, broker status, audit viewer."""

from __future__ import annotations

import json
import os

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from agent_tools import run_agent
from broker import broker
from llm_config import MODEL_NAME, credentials_present

VAULT_AUDIT_LOG = os.getenv("VAULT_AUDIT_LOG", "/vault/logs/vault_audit.log")

app = FastAPI(title="Vault-Brokered Agent Credentials Lab")
templates = Jinja2Templates(directory="templates")

# Chat history for display only — each agent run is single-turn.
chat_history: list[dict] = []


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "history": chat_history,
            "llm_ready": credentials_present(),
            "model_name": MODEL_NAME,
            "active": "chat",
        },
    )


@app.post("/chat", response_class=HTMLResponse)
async def chat(request: Request, question: str = Form(...)):
    try:
        answer, activities = await run_agent(question)
    except Exception as exc:
        answer, activities = f"Agent error: {exc}", []
    chat_history.append({"question": question, "answer": answer, "activities": activities})
    del chat_history[:-20]
    return RedirectResponse("/", status_code=303)


@app.get("/broker", response_class=HTMLResponse)
def broker_page(request: Request):
    return templates.TemplateResponse(
        request,
        "broker.html",
        {"status": broker.status(), "events": broker.events, "active": "broker"},
    )


@app.post("/broker/refresh")
def broker_refresh():
    """Discard the cached DB lease and mint fresh credentials right now, so
    students can watch a new dynamic username appear without waiting for TTL."""
    try:
        broker.get_db_credentials(force_new=True)
    except Exception as exc:
        broker.events.insert(0, {"time": "", "kind": "error", "detail": str(exc)})
    return RedirectResponse("/broker", status_code=303)


def _read_audit_entries(limit: int = 150) -> list[dict]:
    """Parse the tail of Vault's file audit device (JSON lines).

    Note for students: values in the audit log are HMAC'd by Vault — you can
    prove a secret appears in a log entry without the log leaking the secret.
    """
    entries: list[dict] = []
    try:
        with open(VAULT_AUDIT_LOG, "rb") as f:
            lines = f.readlines()[-limit * 2 :]
    except FileNotFoundError:
        return entries
    for line in lines:
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        req = e.get("request", {}) or {}
        auth = e.get("auth", {}) or {}
        entries.append(
            {
                "time": e.get("time", "")[:19].replace("T", " "),
                "type": e.get("type", ""),
                "operation": req.get("operation", ""),
                "path": req.get("path", ""),
                "display_name": auth.get("display_name", ""),
                "policies": ", ".join(auth.get("policies") or []),
                "remote": req.get("remote_address", ""),
                "error": e.get("error", ""),
            }
        )
    entries.reverse()
    return entries[:limit]


@app.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request, path: str = ""):
    entries = _read_audit_entries()
    if path:
        entries = [e for e in entries if path in e["path"]]
    return templates.TemplateResponse(
        request,
        "audit.html",
        {"entries": entries, "filter_path": path, "log_path": VAULT_AUDIT_LOG, "active": "audit"},
    )
