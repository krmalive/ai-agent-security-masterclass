#!/usr/bin/env python3
"""CLI demo for the MCP Tool Poisoning lab (two-server exfiltration).

Runs the insecure or secure agent over STDIO or SSE, then prints what the malicious
SupportDesk server captured — the proof of whether the internal HR directory was exfiltrated.

Examples:
    # STDIO (default) — the agent spawns both MCP servers as subprocesses
    uv run python demo.py --mode insecure
    uv run python demo.py --mode secure

    # SSE — start both servers first, in separate terminals:
    #   uv run python trusted_server.py   --transport sse --port 8002
    #   uv run python malicious_server.py --transport sse --port 8001
    uv run python demo.py --mode insecure --transport sse
"""

import argparse
import asyncio
import json

from insecure_agent import run_agent as insecure_run
from malicious_server import EXFIL_LOG
from secure_agent import run_agent as secure_run

DEFAULT_PROMPT = "Please file a support ticket: my VPN keeps disconnecting from the office network."


async def main() -> None:
    parser = argparse.ArgumentParser(description="MCP tool-poisoning demo")
    parser.add_argument("--mode", choices=["insecure", "secure"], default="insecure")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = parser.parse_args()

    open(EXFIL_LOG, "w").close()  # reset the attacker's capture file

    runner = insecure_run if args.mode == "insecure" else secure_run
    print(f"\n[mode={args.mode} transport={args.transport}] prompt: {args.prompt}\n" + "=" * 60)
    output = await runner(args.prompt, transport=args.transport)
    print("AGENT REPLY:\n" + output)

    print("=" * 60 + "\nATTACKER CAPTURE (exfil_capture.jsonl):")
    captured = [json.loads(l) for l in open(EXFIL_LOG) if l.strip()]
    if not captured:
        print("  (empty — nothing reached the attacker)")
    for entry in captured:
        ctx = entry.get("captured_context", "")
        print(f"  summary : {entry.get('received_summary', '')!r}")
        print(f"  context : {ctx[:400]!r}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
