"""
mcp-weather : a well-behaved backend MCP server.

This is a *simplified* MCP server. Real MCP uses stdio or Streamable-HTTP with a
full JSON-RPC handshake. To keep the lab readable we implement just the three
JSON-RPC methods that matter for the security lesson:

    - initialize
    - tools/list
    - tools/call

The gateway sits in front of this server and never lets a client talk to it
directly. This server has NO authentication of its own -- that is deliberate.
It shows why a gateway is valuable: the backend trusts the network, the gateway
provides the security perimeter.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="mcp-weather")

# ---------------------------------------------------------------------------
# The tools this server exposes. In MCP a tool is (name, description, inputSchema).
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "inputSchema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    },
    {
        "name": "get_forecast",
        "description": "Get a 3-day weather forecast for a city.",
        "inputSchema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    },
]

# Canned data so the lab needs no external API key.
_WEATHER = {
    "london": "12°C, light rain",
    "mumbai": "33°C, humid and sunny",
    "seattle": "9°C, overcast",
}


def _call_tool(name: str, args: dict):
    city = str(args.get("city", "")).strip().lower()
    if name == "get_weather":
        return _WEATHER.get(city, f"18°C, partly cloudy (no live data for '{city}')")
    if name == "get_forecast":
        base = _WEATHER.get(city, "18°C, partly cloudy")
        return f"Day 1: {base}. Day 2: similar. Day 3: clearing up."
    raise ValueError(f"Unknown tool: {name}")


def _jsonrpc_result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


@app.get("/health")
def health():
    return {"status": "ok", "server": "mcp-weather"}


@app.post("/mcp")
async def mcp(request: Request):
    body = await request.json()
    method = body.get("method")
    req_id = body.get("id")
    params = body.get("params") or {}

    if method == "initialize":
        return JSONResponse(_jsonrpc_result(req_id, {"serverInfo": {"name": "mcp-weather"}}))

    if method == "tools/list":
        return JSONResponse(_jsonrpc_result(req_id, {"tools": TOOLS}))

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            text = _call_tool(name, args)
        except ValueError as e:
            return JSONResponse(_jsonrpc_error(req_id, -32602, str(e)))
        return JSONResponse(_jsonrpc_result(req_id, {"content": [{"type": "text", "text": text}]}))

    return JSONResponse(_jsonrpc_error(req_id, -32601, f"Method not found: {method}"))
