"""
agent.py : an MCP client + LLM agent.

It connects to the GATEWAY (never the backends directly), authenticates with a
bearer token, discovers the tools the gateway is willing to expose to that
token, hands them to gpt-4o (via Requesty), and lets the model call them.

Run it with different tokens to see authentication & access control in action,
and after compromising mcp-notes to see that the malicious tool never even
reaches the model.

Usage:
    python agent.py --token tok_alice_weather_001 --prompt "What's the weather in London?"
    python agent.py --token tok_bob_notes_002    --prompt "List my notes"
    python agent.py --token tok_admin_003         --prompt "Add a note that says hello, then list notes"

Environment:
    REQUESTY_API_KEY   required
    GATEWAY_URL        default http://localhost:8080/mcp
"""
import argparse
import json
import os
import sys

import httpx
from openai import OpenAI

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://localhost:8080/mcp")
REQUESTY_API_KEY = os.environ.get("REQUESTY_API_KEY")
MODEL = os.environ.get("MODEL", "openai/gpt-5.6-luna ")


def gateway_rpc(method, params, token):
    """One JSON-RPC call to the gateway with the bearer token attached."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    headers = {"Authorization": f"Bearer {token}"}
    resp = httpx.post(GATEWAY_URL, json=payload, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"gateway returned {resp.status_code}: {resp.text}")
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"gateway error: {data['error']}")
    return data["result"]


def mcp_tools_to_openai(mcp_tools):
    """Convert MCP tool defs into the OpenAI function-calling schema."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
            },
        }
        for t in mcp_tools
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", required=True, help="bearer token to present to the gateway")
    ap.add_argument("--prompt", required=True, help="user prompt for the agent")
    args = ap.parse_args()

    if not REQUESTY_API_KEY:
        sys.exit("ERROR: set REQUESTY_API_KEY in your environment / .env")

    # 1. Discover tools THROUGH the gateway using this token.
    print(f"\n=== Discovering tools with token '{args.token}' ===")
    try:
        result = gateway_rpc("tools/list", {}, args.token)
    except RuntimeError as e:
        sys.exit(f"Auth/list failed: {e}")

    mcp_tools = result.get("tools", [])
    tool_names = [t["name"] for t in mcp_tools]
    print(f"Gateway exposed {len(mcp_tools)} tool(s) to this token: {tool_names}")
    if not mcp_tools:
        print("(No tools available to this token -- the model has nothing to call.)")

    openai_tools = mcp_tools_to_openai(mcp_tools)

    # 2. Ask gpt-4o (via Requesty) to solve the prompt using those tools.
    client = OpenAI(api_key=REQUESTY_API_KEY, base_url="https://router.requesty.ai/v1")
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Use tools when relevant."},
        {"role": "user", "content": args.prompt},
    ]

    print(f"\n=== Asking {MODEL}: {args.prompt!r} ===")
    for _ in range(5):  # allow a few tool-call rounds
        kwargs = {"model": MODEL, "messages": messages}
        if openai_tools:
            kwargs["tools"] = openai_tools
        response = client.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        if not msg.tool_calls:
            print(f"\nASSISTANT: {msg.content}\n")
            return

        messages.append(msg.model_dump())
        for tc in msg.tool_calls:
            name = tc.function.name
            arguments = json.loads(tc.function.arguments or "{}")
            print(f"  -> model calls tool '{name}' with {arguments}")
            try:
                call_result = gateway_rpc(
                    "tools/call", {"name": name, "arguments": arguments}, args.token
                )
                text = call_result.get("content", [{}])[0].get("text", "")
            except RuntimeError as e:
                text = f"[gateway refused: {e}]"
                print(f"     gateway refused the call: {e}")
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": text}
            )

    print("\n(Reached tool-call round limit.)")


if __name__ == "__main__":
    main()
