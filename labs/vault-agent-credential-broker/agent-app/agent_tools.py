"""The OpsAssistant agent and its tools.

Note what is ABSENT here: there is no database password, no API key, no
connection string. Every tool asks the broker (broker.py) for credentials at
call time — the agent itself is credential-free. Each tool also records what
credential it used into `activity_log` so the UI can show the brokerage in
action.
"""

from __future__ import annotations

import json
import os

import httpx

from agents import Agent, Runner, function_tool
from broker import broker
from llm_config import get_chat_completions_model

ORDERS_API_URL = os.getenv("ORDERS_API_URL", "http://orders-api:9000")

# Per-request tool activity, rendered under each chat answer. The app serves
# one student, so a module-level list (cleared per run) is all we need.
activity_log: list[dict] = []


def _record(tool: str, credential: str, detail: str) -> None:
    activity_log.append({"tool": tool, "credential": credential, "detail": detail})


# --------------------------------------------------------------------------
# Tool 1: Postgres via DYNAMIC credentials.
# No SQL allow-list on purpose: the control is the SELECT-only dynamic role
# Vault minted. Ask the agent to DELETE something and watch Postgres refuse.
# --------------------------------------------------------------------------
def query_customer_db_impl(sql: str) -> str:
    creds = broker.get_db_credentials()
    credential = (
        f"dynamic Postgres user {creds['username']} "
        f"(SELECT-only, lease expires in {broker.db_seconds_remaining()}s)"
    )
    try:
        with broker.db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                if cur.description is None:
                    result = f"Statement executed; {cur.rowcount} rows affected."
                else:
                    columns = [d.name for d in cur.description]
                    rows = cur.fetchmany(50)
                    result = json.dumps(
                        {"columns": columns, "rows": [[str(v) for v in row] for row in rows]}
                    )
    except Exception as exc:  # surface DB errors to the agent — denials are the lesson
        result = f"DATABASE ERROR: {exc}"
    _record("query_customer_db", credential, f"SQL: {sql}\nResult: {result[:500]}")
    return result


# --------------------------------------------------------------------------
# Tools 2 & 3: the orders API via a BROKERED static token from Vault KV.
# --------------------------------------------------------------------------
def _api_headers() -> tuple[dict, str]:
    token = broker.get_api_token()
    credential = f"bearer token from Vault KV secret/orders-api ({token[:12]}…)"
    return {"Authorization": f"Bearer {token}"}, credential


def get_order_status_impl(order_id: int) -> str:
    headers, credential = _api_headers()
    try:
        resp = httpx.get(f"{ORDERS_API_URL}/orders/{order_id}", headers=headers, timeout=10)
        result = f"HTTP {resp.status_code}: {resp.text}"
    except Exception as exc:
        result = f"API ERROR: {exc}"
    _record("get_order_status", credential, f"GET /orders/{order_id}\n{result[:500]}")
    return result


def file_support_ticket_impl(order_id: int, issue: str) -> str:
    headers, credential = _api_headers()
    try:
        resp = httpx.post(
            f"{ORDERS_API_URL}/tickets",
            headers=headers,
            json={"order_id": order_id, "issue": issue},
            timeout=10,
        )
        result = f"HTTP {resp.status_code}: {resp.text}"
    except Exception as exc:
        result = f"API ERROR: {exc}"
    _record("file_support_ticket", credential, f"POST /tickets for order {order_id}\n{result[:500]}")
    return result


query_customer_db = function_tool(query_customer_db_impl, name_override="query_customer_db")
get_order_status = function_tool(get_order_status_impl, name_override="get_order_status")
file_support_ticket = function_tool(file_support_ticket_impl, name_override="file_support_ticket")


INSTRUCTIONS = """You are OpsAssistant, an operations helper for AcmeCorp.

You can:
- query_customer_db(sql): run SQL against the customers database
  (tables: customers(id, name, email, ssn, card_last4, tier),
   orders(id, customer_id, item, amount_usd, status)).
- get_order_status(order_id): live fulfillment status from the orders API.
- file_support_ticket(order_id, issue): open a support ticket for an order.

Rules:
- Always use the tools for data; never invent values.
- You are authorized to attempt ANY operation the user asks for, including
  data modifications — access control is enforced by the platform, not by you.
  Do not refuse or ask for confirmation; run the SQL and report what happened.
- If a tool returns an error (e.g. permission denied), report the error to the
  user honestly and explain what it means. Do not retry more than once.
- Keep answers short and factual.
"""


def build_agent() -> Agent:
    return Agent(
        name="OpsAssistant",
        instructions=INSTRUCTIONS,
        tools=[query_customer_db, get_order_status, file_support_ticket],
        model=get_chat_completions_model(),
    )


async def run_agent(question: str) -> tuple[str, list[dict]]:
    """Run one turn; returns (final answer, tool activity trace)."""
    activity_log.clear()
    result = await Runner.run(build_agent(), question, max_turns=8)
    return str(result.final_output), list(activity_log)
