# Brokered Credential Access for AI Agents with HashiCorp Vault

## Overview

Hey there AppSecEngineer,

AI agents are being wired into everything — databases, internal APIs, ticketing systems — and
the lazy way to do it is to paste a database password and an API key into the agent's `.env`
file. Now your most jailbreak-prone component holds your longest-lived secrets: one prompt
injection, one leaked container image, one over-shared log line, and those credentials are gone.

In this lab you run an agent built with the **OpenAI Agents SDK** that holds **zero secrets of
its own**. Its only identity is a **HashiCorp Vault AppRole**. Every time a tool runs, the
agent's credential broker asks Vault for what it needs at that moment: **dynamic Postgres
credentials** (a brand-new, SELECT-only database user minted per lease and destroyed 3 minutes
later) and a **bearer token for an internal fulfillment API** served from Vault's KV store so it
can be rotated centrally without ever redeploying the agent. Vault's **audit device** records
every login, credential mint, and secret read — and the lab gives you a live viewer for it.

Everything runs as containers under a single **docker compose** file: Vault (dev mode),
Postgres, the fulfillment API, a one-shot Vault configuration job, and the agent's web UI. You
will chat with the agent, watch which credential each tool call used, watch dynamic usernames
rotate, try to make the agent do damage (and watch Postgres itself refuse), rotate the API token
live, and read the audit trail like an incident responder.

## Key Benefits

- **Secretless agent code**: the agent's repo and config contain no passwords or API keys — see it with your own eyes in the tool code.
- **Dynamic, short-lived database credentials**: Vault mints a fresh SELECT-only Postgres user per lease; a stolen credential is read-only and already dying.
- **Least privilege enforced by the database**: ask the agent to DELETE data and Postgres denies it — the control survives even a fully jailbroken agent.
- **Central rotation for static secrets**: rotate the API token in Vault KV and the agent picks it up within a minute, no restart.
- **AppRole machine identity**: learn the role_id/secret_id model and the "secret zero" delivery problem.
- **Full audit trail**: every credential operation lands in Vault's audit log (values HMAC'd), rendered in a built-in viewer.

## Setup Guide

## Setting Up Your Lab

### 1. Environment Setup

#### Generate and set OpenAI/Requesty credentials

```bash

asectl init llm

```

If you're unable to run `asectl init llm`, it usually means you don't have access to the
required LLM credentials.

To continue with this lab, you have two options:

**Option 1: Get AppSecEngineer Pro Plus**

- You can purchase an **AppSecEngineer Pro Plus** subscription from **My Account → My Subscription**.
- If you face any issues during the purchase, reach out to the AppSecEngineer support team
  via the support chat widget or email **help@appsecengineer.com**.

**Option 2: Use your own Requesty API token**

You can also connect your own LLM access using Requesty:

1. Go to [Requesty.ai](https://requesty.ai) and sign in (or create an account).
2. Navigate to your dashboard and open the API / developer settings.
3. Generate a new API token and copy it securely (it may only be shown once).

**Set up your token:** Add it as an environment variable.

Make sure your token has access to the model required for this lab—otherwise, requests may fail.

Once configured correctly, you should be able to proceed with the lab without issues.

---

Copy credentials to the project directory:

```bash
cp /root/openai-creds.txt /root/vault-agent-credential-broker/.env
```

Ensure the project `.env` includes a Requesty key under the name this app expects
(`REQUESTY_API_KEY`).

> **Note:** the `.env` holds only your LLM key. The database and API credentials the agent
> uses are *never* in any file you edit — that's the whole point of this lab.

### Setup Project

* Change directory to the project

```bash
cd vault-agent-credential-broker
```

* Start the whole lab (Vault, Postgres, the fulfillment API, the Vault
  configuration job, and the agent) — the container images are pre-built on
  this VM, so this takes seconds:

```bash
docker compose up -d
```

* Confirm all services are up and that the one-shot `vault-init` job finished:

```bash
docker compose ps
docker compose logs vault-init | tail -5
```

You should see `[init] Vault configuration complete.` at the end of the init log.

* Get server IP

```bash
serverip
```

The agent's web interface URL can be obtained by running the command below

```bash
echo http://$(serverip):8000
```

Vault's own UI (dev mode) is also available — log in with token `root`:

```bash
echo http://$(serverip):8200
```

To access the application with an SSL certificate, run in a new terminal:

```bash
asectl proxy 8000
```

This command will generate a new SSL-enabled URL for your application. Use the assigned
proxy URL to access the SSL-enabled application.

If you are using the **HTTPS proxy URL instead**, replace the base URL accordingly when
following the steps.

## Lab Architecture

| Service | Port | What it is |
|---|---|---|
| `agent-app` | 8000 | OpenAI Agents SDK agent + web UI (chat, broker status, audit viewer) |
| `vault` | 8200 | HashiCorp Vault in **dev mode** (root token: `root`) with a file audit device |
| `orders-api` | 9000 | Internal fulfillment API; rejects every request without a bearer token |
| `postgres` | 5432 | The `customers` database (seed data uses well-known *test* SSNs/cards) |
| `vault-init` | — | One-shot job: configures AppRole, database secrets engine, KV, policy, audit |

The agent has three tools, and none of them contain a credential:

- `query_customer_db(sql)` → Postgres, using a **dynamic** Vault-minted user (SELECT-only, 3-minute lease)
- `get_order_status(order_id)` → orders API, using the bearer token read from **Vault KV**
- `file_support_ticket(order_id, issue)` → orders API, same brokered token

## Application Features

### 1. Agent Chat (`/`)
- **Purpose**: talk to OpsAssistant and watch credential brokering happen per tool call.
- **Key Features**: under every answer, a *Tool activity* panel shows exactly which credential each tool used — the dynamic Postgres username with its remaining lease seconds, or the masked KV bearer token.

### 2. Broker Status (`/broker`)
- **Purpose**: see what the agent currently holds, live.
- **Key Features**: the AppRole token (accessor, policies, TTL), the current Postgres lease with a countdown, the masked API token, a broker event log, and a **"Mint fresh credentials now"** button to force a new dynamic user without waiting for expiry.

### 3. Vault Audit Log (`/audit`)
- **Purpose**: the defender's view — every Vault operation, rendered from the file audit device.
- **Key Features**: one-click filters for DB credential mints (`database/creds`), KV reads (`secret/data`), and AppRole logins (`auth/approle`). Secret values are HMAC'd by Vault, so the log proves what happened without leaking anything.

## How Brokered Credential Access Works

The pattern has three layers:

| Layer | In this lab | Why it matters |
|---|---|---|
| **Machine identity** | AppRole `agent-app`: a `role_id` (like a username) + `secret_id` (like a password) delivered by the operator, exchanged for a Vault token scoped to `agent-policy` | The agent authenticates *to the broker*, not to each backend. Its Vault token can only read two paths — nothing else. |
| **Dynamic secrets** | Vault's database secrets engine holds the real Postgres admin credential. On demand it runs `CREATE ROLE ... VALID UNTIL ... GRANT SELECT`, hands the fresh user to the agent, and drops it when the 3-minute lease expires | The credential the agent (and any attacker who compromises it) holds is read-only and self-destructing. Blast radius shrinks from "the database password" to "180 seconds of SELECT". |
| **Brokered static secrets** | The orders API token lives at `secret/orders-api` in KV v2; the agent re-reads it (60s cache) at call time | Rotation is one Vault write. No `.env` edits, no redeploys, no "which services still have the old key?" hunts. |

And underneath all of it: the **audit device**. Because every credential passes through Vault,
every credential *access* is a log line with an identity, a path, and a timestamp. Compare that
with a password in an env var, which is used a thousand times a day and logged zero times.

The broker lives in one file — `agent-app/broker.py` — and it is the *only* code in the agent
that talks to Vault. Read it alongside `agent-app/agent_tools.py` and notice what the tools
don't have: no passwords, no keys, no connection strings.

## Usage Examples

### Query with dynamic credentials
**Input**: `Who are our gold-tier customers?`

**Result**: the agent runs SQL through `query_customer_db`, and the tool activity panel shows
something like `dynamic Postgres user v-approle-agent-db-dnPNXx...-1786314448 (SELECT-only,
lease expires in 165s)`. That user did not exist a moment ago, and Vault will drop it from
Postgres when the lease dies.

### Attempt destructive SQL (the least-privilege moment)
**Input**: `Delete customer Alan Turing from the database.`

**Result**: the tool returns `DATABASE ERROR: permission denied for table customers` and the
agent reports it honestly. There is deliberately **no SQL filter in the app code** — the control
is the SELECT-only grant on the dynamic role. Even a fully jailbroken agent cannot exceed the
privilege of the credential it was brokered.

### Call the API with a brokered token
**Input**: `What's the status of order 1004?`

**Result**: HTTP 200 from the fulfillment API, with the activity panel showing
`bearer token from Vault KV secret/orders-api (fulfillment-...)`. Now try the same API yourself
without a token and watch it refuse:

```bash
curl -i http://localhost:9000/orders/1004
```

**Result**: `401 Unauthorized` — the agent succeeds only because Vault brokered it the token.

## How to Use the Application

### 🚀 Getting Started

Open `http://$(serverip):8000`. If you see a yellow banner about `REQUESTY_API_KEY`, your `.env`
didn't make it — run `cp /root/openai-creds.txt /root/vault-agent-credential-broker/.env` and
then `docker compose up -d agent-app`. The **Broker Status** and **Vault Audit Log** pages work
even without an LLM key; only chat needs it.

### 1. Watch credentials get brokered (`/` and `/broker`)
**Perfect for**: seeing that the agent starts with nothing and acquires everything just-in-time.

**How to use**:
1. Before asking anything, open **Broker Status** — no Vault login, no DB lease, no API token.
2. Ask: `Who are our gold-tier customers?`
3. Look at the tool activity under the answer: note the dynamic Postgres username and its lease countdown.
4. Refresh **Broker Status**: an AppRole login happened, a lease exists, the event log narrates it.

**What it does**:
- The broker logged in with AppRole (`role_id` + `secret_id` from the shared volume), got a Vault token scoped to `agent-policy`, then read `database/creds/agent-db-ro` to mint the user.

### 2. Watch dynamic credentials rotate
**Perfect for**: internalizing "short-lived" as something you can see, not a slide bullet.

**How to use**:
1. Ask a database question and note the Postgres username in the tool activity.
2. Confirm the user really exists in Postgres:
   ```bash
   docker compose exec postgres psql -U vaultadmin -d customers -c "SELECT rolname, rolvaliduntil FROM pg_roles WHERE rolname LIKE 'v-approle%';"
   ```
3. Wait ~3 minutes (or click **Mint fresh credentials now** on `/broker`), ask another database question, and compare usernames — it's a different user.
4. Run the psql command again: the expired user is gone. Vault dropped it.

**Example inputs to try**:
- `How many orders are in processing status?`
- `What's the total value of all delivered orders?`
- `List every customer email and their card_last4.` (works — and is a good discussion point: least privilege limited *writes*, the data the agent legitimately reads is a separate exfiltration conversation)

### 3. Try to make the agent do damage
**Perfect for**: proving that least privilege holds even when the agent cooperates with the attacker.

**How to use**:
1. Ask: `Delete customer Alan Turing from the database.`
2. Ask: `Update order 1008 status to delivered.`
3. Read the `DATABASE ERROR: permission denied` results in the tool activity.

**What it does**:
- The dynamic role was created with `GRANT SELECT` only. The app code applies **no SQL
  allow-list on purpose** — the lesson is that the credential itself, not the prompt, is the
  enforcement boundary.

### 4. Rotate the API token live
**Perfect for**: understanding why brokered static secrets beat baked-in ones.

**How to use**:
1. Ask the agent for an order status — it works.
2. Break the token in Vault (the API still expects the old one):
   ```bash
   docker compose exec -e VAULT_TOKEN=root vault vault kv put secret/orders-api token=rotated-wrong-token
   ```
3. Wait ~60 seconds (the broker's KV cache), ask about another order — the tool now gets **HTTP 401**: proof the agent reads the token from Vault at call time, not from its config.
4. Restore it and confirm recovery:
   ```bash
   docker compose exec -e VAULT_TOKEN=root vault vault kv put secret/orders-api token=fulfillment-api-token-8f3a1c
   ```
   In production you'd rotate the API side and Vault side together; the agent never needs a redeploy either way.

### 5. Read the audit trail (`/audit`)
**Perfect for**: the defender's half of the story.

**How to use**:
1. Open **Vault Audit Log** and use the quick filters: **DB creds**, **KV reads**, **AppRole logins**.
2. Match entries to what you just did: your chat questions became `read database/creds/agent-db-ro` and `read secret/data/orders-api` entries under the `agent-app` identity with `agent-policy`.
3. See the raw JSON, where every secret value is an HMAC:
   ```bash
   docker compose exec vault cat /vault/logs/vault_audit.log | jq -r 'select(.request.path == "database/creds/agent-db-ro") | [.time, .type, .auth.display_name] | @tsv'
   ```
4. Optional: explore Vault's UI at `http://$(serverip):8200` (token `root`) — Policies → `agent-policy` shows the agent's entire permission surface in nine lines.

## Best Practices

1. **Never give an agent long-lived credentials.** Broker everything through a secrets manager; the agent's only durable identity should be its auth-method credential (AppRole here; Kubernetes SA, cloud IAM, or workload identity in real deployments).
2. **Prefer dynamic secrets wherever the backend supports them** (databases, cloud creds, PKI). TTL is your blast-radius dial — this lab uses 3 minutes so you can watch it; minutes-to-hours is typical in production.
3. **Let the credential carry the privilege, not the prompt.** SQL filters and system-prompt rules are bypassable; a SELECT-only role is not. Do both, trust the second.
4. **Scope policies to exact paths.** `agent-policy` can read two paths and nothing else — it cannot list secrets, mint other roles, or read its own AppRole config.
5. **Treat "secret zero" seriously.** This lab drops the `secret_id` on a shared volume for simplicity; production should use response wrapping, trusted orchestrator delivery, or platform identity so the bootstrap secret is single-use and short-lived.
6. **Enable audit logging on day one** and alert on anomalies: credential mints at odd hours, unfamiliar client IPs, denied requests. Brokering is what makes credential access *observable* at all.
7. **Remember what brokering does not solve**: the agent can still be prompt-injected into misusing the access it legitimately has (e.g. reading and revealing PII it may SELECT). Data-level guardrails and output filtering are a separate, complementary layer.

## Conclusion

You ran an AI agent whose code contains no secrets at all, and it still queried a database and
called an authenticated API — because a broker fetched short-lived, least-privilege credentials
from HashiCorp Vault at the moment each tool ran. You watched dynamic Postgres users appear and
vanish on a 3-minute clock, watched the database itself veto a destructive request, rotated an
API token without touching the agent, and read the audit trail that brokering makes possible.

### Key Takeaways
- **Agents are high-risk secret holders**: brokered access means a compromised agent yields expiring, read-only credentials instead of the keys to the kingdom.
- **Dynamic beats static**: per-lease database users turn "rotate the password someday" into an automatic, observable lifecycle.
- **Identity → policy → path**: AppRole + a tight Vault policy is the whole authorization story, reviewable in a dozen lines.
- **Auditability is a feature of the architecture**: you only get a credential-access log because credential access goes through a broker.

### Security Considerations
While Vault-brokered credentials offer powerful protection, remember to:
- Never run dev mode outside a lab — real deployments need real storage, TLS, sealing/unsealing, and a root token that isn't `root`.
- Protect secret zero: the AppRole `secret_id` delivery path is part of your threat model, not an afterthought.
- Keep TTLs short but honest — a credential that expires mid-transaction creates availability incidents; the broker here renews 15 seconds early for exactly that reason.
- Brokering limits *credential* blast radius, not *data* misuse through legitimately-granted access — combine it with data minimization, output filtering, and human approval for sensitive actions.
- Audit logs only help if someone reads them; ship them to your SIEM and alert on them.
