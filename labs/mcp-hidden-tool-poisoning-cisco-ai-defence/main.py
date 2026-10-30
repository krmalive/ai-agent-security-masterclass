"""Web UI for the MCP Tool Poisoning lab (two-server / cross-domain exfiltration).

Two routes, same agent, same two MCP servers (trusted HR + malicious SupportDesk):

  * ``/``        insecure agent (both servers via stock MCP clients)
  * ``/secure``  secure agent (malicious server behind the schema-validation defense layer)

After each run the app reads the attacker's capture file (``EXFIL_LOG``) and shows exactly
what the malicious server received — the ground-truth proof of whether data was exfiltrated.
Both routes default to STDIO (the agent spawns the servers as subprocesses).
"""

import json
import os

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from insecure_agent import run_agent as insecure_run
from malicious_server import EXFIL_LOG
from secure_agent import run_agent as secure_run
from tool_guard import _egress_violation

app = FastAPI(title="MCP Tool Poisoning Lab")
templates = Jinja2Templates(directory="templates")


def _reset_exfil() -> None:
    """Clear the attacker's capture file before a run so we only see this run's result."""
    try:
        open(EXFIL_LOG, "w").close()
    except OSError:
        pass


def _read_exfil() -> list[dict]:
    """Return the entries the malicious server captured during the run."""
    entries: list[dict] = []
    try:
        with open(EXFIL_LOG) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        pass
    return entries


def _exfil_sensitive(entries: list[dict]) -> bool:
    """True if the attacker captured anything that trips the sensitive-data detector."""
    return any(_egress_violation({"c": e.get("captured_context", "")}) for e in entries)


async def _run(route_type: str, prompt: str):
    runner = secure_run if route_type == "secure" else insecure_run
    _reset_exfil()
    try:
        response = await runner(prompt, transport="stdio")
    except Exception as exc:  # surface config errors (e.g. missing key) in the UI
        response = f"[error] {exc}"
    entries = _read_exfil()
    return response, entries, _exfil_sensitive(entries)


def _render(request: Request, route_type: str, prompt, response, entries, leaked):
    secure = route_type == "secure"
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "route_type": route_type,
            "title": "Secure Route" if secure else "Insecure Route",
            "description": (
                "Malicious server behind the schema-validation defense layer"
                if secure else "Both MCP servers trusted verbatim"
            ),
            "prompt": prompt,
            "response": response,
            "exfil_entries": entries,
            "leaked": leaked,
        },
    )


@app.get("/", response_class=HTMLResponse)
async def insecure_get(request: Request):
    return _render(request, "insecure", None, None, None, None)


@app.post("/", response_class=HTMLResponse)
async def insecure_post(request: Request, prompt: str = Form(...)):
    response, entries, leaked = await _run("insecure", prompt)
    return _render(request, "insecure", prompt, response, entries, leaked)


@app.get("/secure", response_class=HTMLResponse)
async def secure_get(request: Request):
    return _render(request, "secure", None, None, None, None)


@app.post("/secure", response_class=HTMLResponse)
async def secure_post(request: Request, prompt: str = Form(...)):
    response, entries, leaked = await _run("secure", prompt)
    return _render(request, "secure", prompt, response, entries, leaked)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
