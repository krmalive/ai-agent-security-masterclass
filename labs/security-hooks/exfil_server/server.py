"""Mock attacker listener for the security-hooks lab.

Captures POSTs to /keys and displays them in a web dashboard at http://localhost:8000
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI(title="exfil-listener (mock)")

_HITS: list[dict] = []
_DASHBOARD_HTML = (Path(__file__).parent / "dashboard.html").read_text()


async def _capture(request: Request) -> dict:
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    raw = (await request.body()).decode("utf-8", errors="replace")
    body_json = None
    if raw.strip():
        try:
            body_json = json.loads(raw)
        except Exception:  # noqa: BLE001
            body_json = None

    client = request.client.host if request.client else "unknown"
    display = json.dumps(body_json, indent=2) if body_json is not None else raw

    record = {
        "id": len(_HITS) + 1,
        "ts": ts,
        "method": request.method,
        "path": request.url.path,
        "client": client,
        "query": dict(request.query_params),
        "raw": display,
        "size": len(raw.encode("utf-8")),
    }
    _HITS.append(record)

    print(f"[exfil] capture #{record['id']} from {client} — open http://localhost:8000")
    return record


@app.api_route("/keys", methods=["GET", "POST", "PUT"])
async def keys(request: Request):
    record = await _capture(request)
    return {"status": "received", "captured": record}


@app.get("/api/hits")
async def api_hits():
    return {"count": len(_HITS), "hits": _HITS}


@app.get("/hits")
async def hits():
    """JSON alias kept for README / scripts."""
    return await api_hits()


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return _DASHBOARD_HTML


def main() -> None:
    print("Exfil listener → http://localhost:8000")
    print("Agent payload target → http://localhost:8000/keys")
    print("Leave this running, then run the lab in another terminal.\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
