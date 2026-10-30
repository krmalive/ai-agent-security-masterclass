# Detecting MCP Tool Poisoning with the Cisco AI Defense MCP Scanner

## Overview

Hey there AppSecEngineer,

In this lab you step into the shoes of a **supply-chain security engineer**. Your team is about
to wire a set of third-party **Model Context Protocol (MCP)** servers into an AI agent, and your
job is to vet them *before* they touch production. One of those servers looks perfectly ordinary
— it exposes a friendly `submit_support_ticket` tool — but its tool description is **poisoned**:
hidden instructions tell the agent to secretly pull the company's internal HR directory and smuggle
it out inside a support ticket. This is a **tool poisoning** attack, and by the time an agent
executes it, the data is already gone.

Rather than reading every tool description by hand (which does not scale, and misses cleverly
obfuscated payloads), you will use the **open-source [Cisco AI Defense MCP Scanner](https://github.com/cisco-ai-defense/mcp-scanner)**
(`cisco-ai-mcp-scanner`) to scan the servers statically. The scanner connects to an MCP server,
enumerates its tools, prompts and resources, and runs them through up to three detection engines —
**YARA** pattern rules, an **LLM-as-judge**, and the hosted **Cisco AI Defense** inspection API.
You will scan a clean server and a poisoned one, learn to read the findings and map them to the
MCP threat taxonomy, and then run the vulnerable agent to watch the exfiltration you predicted
actually happen.

The star of this lab is **detection and triage**, not writing a defense. You will finish able to
add MCP scanning to a review workflow or a CI/CD pipeline so poisoned tools are caught at the door.

## Key Benefits
- **Catch tool poisoning before an agent runs it**: scan third-party MCP servers as a pre-connection gate.
- **Hands-on with a real open-source scanner**: the same `cisco-ai-mcp-scanner` engine used in Cisco's IDE AI Security Scanner and DefenseClaw.
- **Read findings like an analyst**: map scanner output to the MCP threat taxonomy (Direct Prompt Injection, Data Exfiltration via Agent Tooling).
- **Signal vs. noise**: see a clean server score SAFE and a poisoned one score HIGH — the contrast is the lesson.
- **Three engines, one workflow**: start with keyless YARA, then layer in LLM-as-judge and the Cisco AI Defense API for semantic depth.
- **CI/CD ready**: learn the offline `static` scan mode you can drop into a pipeline.

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
cp /root/openai-creds.txt /root/mcp-hidden-tool-poisoning-lab/.env
```

Ensure the project `.env` includes a Requesty key under the name this app expects
(`REQUESTY_API_KEY`).

> **Note:** The YARA-only scans that form the core of this lab need **no credentials at all**.
> You only need the Requesty key for the *impact* step (running the vulnerable agent) and for the
> optional LLM-as-judge / behavioral engines later on.

### Setup Project

* Change directory to the project

```bash
cd mcp-hidden-tool-poisoning-lab
```

* Install dependencies (this also installs the Cisco AI Defense MCP Scanner)

```bash
uv sync
```

* Confirm the scanner is available

```bash
uv run mcp-scanner --help
```

You should see the scanner's usage banner listing subcommands like `stdio`, `remote`, `static`
and `behavioral`. If you see that, you're ready.

## The Servers You're Vetting

This lab ships two MCP servers. They are ordinary Python MCP servers — exactly the kind you would
receive from an internal team or a third-party vendor.

| Server | Role | What to expect |
|---|---|---|
| `trusted_server.py` | **Internal HR Directory** — a legitimate server the agent is authorized to read. Exposes `get_employee_directory` (holds fake test SSNs/salaries). | A clean bill of health. |
| `malicious_server.py` | **SupportDesk Integration** — an attacker-controlled third-party server. Exposes `submit_support_ticket`, whose description is poisoned. | HIGH-severity findings. |

Open `malicious_server.py` and read the docstring of `submit_support_ticket`. Notice the
`<IMPORTANT>` block instructing the agent to first call `get_employee_directory` and paste its
**entire** output into the ticket's `context` — and to never tell the user. That is the poison.
Your scanner needs to catch it without you having to spot it by eye.

## How MCP Scanning Works

The Cisco AI Defense MCP Scanner treats an MCP server the way an attacker's *victim agent* would:
it connects, calls `tools/list`, and reads every tool name, description and input schema (plus
prompts and resources). It then runs that surface through one or more analyzers:

| Engine | Needs a key? | What it catches |
|---|---|---|
| **YARA** (`yara`) | No | Pattern-based signatures for prompt-injection markup and data-exfiltration language embedded in tool metadata. Fast, deterministic, CI-friendly. |
| **LLM-as-judge** (`llm`) | Yes (LLM key) | Semantic analysis — catches paraphrased or obfuscated poisoning that no static rule matches. |
| **Cisco AI Defense API** (`api`) | Yes (Cisco key) | Cloud threat intelligence via Cisco's hosted inspection API. |

Every finding is mapped to an **MCP threat taxonomy** entry (e.g. *Direct Prompt Injection*,
*Data Exfiltration via Agent Tooling*) with a severity, so you can triage and report consistently.

## Usage Examples

### Baseline: scan the trusted server (expect SAFE)

**Input:**

```bash
uv run mcp-scanner --analyzers yara --format summary stdio \
  --stdio-command uv --stdio-arg run --stdio-arg python --stdio-arg trusted_server.py
```

**Result:** The scanner spawns the trusted server over stdio, lists its one tool, and reports:

```
=== MCP Scanner Results Summary ===

Scan Target: stdio:uv run python trusted_server.py
Total tools scanned: 1
Safe items: 1
Unsafe items: 0

=== Safe Items ===
1. get_employee_directory (tool) - SAFE (0 findings)
```

A legitimate server holding sensitive data still scans clean — sensitivity of *data* is not the
signal; **poisoned instructions** are. This is your baseline for what "good" looks like.

### The catch: scan the malicious server (expect HIGH)

**Input:**

```bash
uv run mcp-scanner --analyzers yara --format summary stdio \
  --stdio-command uv --stdio-arg run --stdio-arg python --stdio-arg malicious_server.py
```

**Result:**

```
=== MCP Scanner Results Summary ===

Scan Target: stdio:uv run python malicious_server.py
Total tools scanned: 1
Safe items: 0
Unsafe items: 1

=== Unsafe Items ===
1. submit_support_ticket (tool) - HIGH (2 findings)
```

The scanner flagged the poisoned tool **without executing it and without you reading a single line
of its description.** That is the point: detection scales, eyeballs do not.

## How to Use the Application

### 🚀 Getting Started

Everything runs from `/root/mcp-hidden-tool-poisoning-lab`. The YARA exercises need no
credentials. If a later step complains about a missing key, revisit **Environment Setup** — the
agent-impact step and the optional LLM engines read `REQUESTY_API_KEY` from your `.env`.

### 1. Baseline scan — the trusted server

**Perfect for**: establishing what a clean result looks like before you judge a suspicious one.

**How to use**:
1. Run the trusted-server summary scan from *Usage Examples* above.
2. Confirm you get `SAFE (0 findings)`.

**What it does**:
- Connects to the internal HR server, enumerates `get_employee_directory`, and finds no
  injected instructions in its metadata.

### 2. Detection scan — the malicious server (detailed)

**Perfect for**: the core skill — reading and triaging a real finding.

**How to use**:
1. Run the detailed scan:

```bash
uv run mcp-scanner --analyzers yara --format detailed stdio \
  --stdio-command uv --stdio-arg run --stdio-arg python --stdio-arg malicious_server.py
```

**What it does** — you'll see output like:

```
Tool 1: submit_support_ticket
Safe: No
Analyzer Results:
  • yara_analyzer:
    - Severity: HIGH
    - Threat Summary: Detected 2 threats: prompt injection, data exfiltration
    - Threat Names: PROMPT INJECTION, DATA EXFILTRATION
    - MCP Taxonomies (2 unique threats):
      [1] Direct Prompt Injection
          • AITech: AITech-1.1
          • AISubtech Name: Instruction Manipulation (Direct Prompt Injection)
      [2] Data Exfiltration / Exposure
          • AITech: AITech-8.2
          • AISubtech Name: Data Exfiltration via Agent Tooling
```

Read it like an analyst:
- **Direct Prompt Injection** → the `<IMPORTANT>` block trying to override the agent's behavior.
- **Data Exfiltration via Agent Tooling** → the instruction to copy the directory into an argument
  that leaves the trust boundary.

Together they *are* the tool-poisoning attack, named and classified.

**Example variations to try**:
- Swap `--format detailed` for `--format by_severity` or `--format table`.
- Add `--severity-filter high` to show only the serious findings.
- Scan a single tool with the `--stdio-tool submit_support_ticket` option.

### 3. Prove the impact — run the vulnerable agent

**Perfect for**: connecting a *scanner finding* to *real-world consequence*, so the HIGH severity
isn't abstract.

**How to use**:
1. Make sure your `.env` has a working `REQUESTY_API_KEY` (see Environment Setup).
2. Run the insecure agent over stdio:

```bash
uv run python demo.py --mode insecure
```

3. Then inspect what the attacker captured:

```bash
cat exfil_capture.jsonl
```

**What it does**:
- The agent connects to *both* servers, reads the poisoned description, pulls the HR directory
  from the trusted server, and pastes it into the support ticket sent to the attacker.
- `exfil_capture.jsonl` is the attacker's loot file — it will contain the internal directory
  (fake SSNs and salaries). That file is the ground-truth proof the poisoning you *detected* in
  step 2 actually *fires* when an agent trusts the tool.

You can also see this side-by-side in the web UI:

```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Get the URL with:

```bash
echo http://$(serverip):8000
```

To access it over SSL, run in a new terminal:

```bash
asectl proxy 8000
```

This generates an SSL-enabled URL. Use the assigned proxy URL to access the application. If you
use the **HTTPS proxy URL instead**, replace the base URL accordingly.

### 4. (Advanced) Add semantic engines — LLM-as-judge & behavioral

**Perfect for**: catching poisoning that has been *reworded* to slip past static YARA rules.

The LLM engines reuse the same Requesty router the lab already uses. Point the scanner at it:

```bash
export MCP_SCANNER_LLM_API_KEY="$REQUESTY_API_KEY"
export MCP_SCANNER_LLM_BASE_URL="https://router.requesty.ai/v1"
export MCP_SCANNER_LLM_MODEL="openai/gpt-4.1-mini"
```

Then run the scanner with all available analyzers:

```bash
uv run mcp-scanner --analyzers yara,llm --format detailed stdio \
  --stdio-command uv --stdio-arg run --stdio-arg python --stdio-arg malicious_server.py
```

Or run the **behavioral** analyzer, which inspects the server's *source code* for mismatches
between what a tool says it does and what it actually does (the malicious tool claims to file a
ticket but also writes your data to disk):

```bash
uv run mcp-scanner behavioral --format detailed malicious_server.py
```

> **Caveat**: the LLM and behavioral engines are non-deterministic and depend on your Requesty
> token having access to the chosen model. If they error with "LLM provider API key is required",
> re-check the three `MCP_SCANNER_LLM_*` variables above. YARA remains your reliable, keyless
> baseline.

### 5. (Advanced) Scan over SSE, or offline in CI/CD

**Scan a running server over SSE** (mirrors how you'd scan a *deployed* remote MCP server):

```bash
# Terminal 1 — start the malicious server as a long-running SSE service
uv run python malicious_server.py --transport sse --port 8001

# Terminal 2 — scan the remote endpoint
uv run mcp-scanner --analyzers yara --format summary remote \
  --server-url http://localhost:8001/sse
```

**Offline / CI-CD mode**: export an MCP server's tool surface to JSON and scan it with the
`static` subcommand — no live server needed. This is the shape you'd wire into a pipeline so a
poisoned tool fails the build:

```bash
uv run mcp-scanner static --help
```

## Best Practices
1. **Scan before you connect.** Treat every third-party MCP server as untrusted until scanned —
   the attack completes the instant a trusting agent runs the tool.
2. **Start with YARA, escalate to LLM.** Keyless YARA gives you a fast, deterministic gate; add
   the LLM-as-judge and Cisco AI Defense API for obfuscated payloads that dodge static rules.
3. **Gate your pipeline.** Use the `static` scan mode in CI/CD and fail the build on HIGH findings
   so a poisoned server can't merge.
4. **Read the taxonomy, not just the severity.** The threat names (*Direct Prompt Injection*,
   *Data Exfiltration via Agent Tooling*) tell you *how* the tool is dangerous, which drives your
   remediation.
5. **Detection is layer one, not the whole story.** A clean scan lowers risk but isn't a guarantee;
   pair scanning with runtime controls (least privilege for tools, egress/DLP checks, human review
   of cross-domain actions).

## Conclusion

You just ran a security engineer's pre-flight check on a set of MCP servers: a clean internal
server passed, an attacker-controlled server was caught red-handed with a HIGH-severity tool
poisoning finding, and you confirmed the impact by watching the agent exfiltrate the HR directory
into the attacker's capture file. Crucially, the scanner found the threat *without executing it and
without you reading the poison by hand* — which is exactly what makes detection scale to the
hundreds of MCP servers a real agent ecosystem will pull in.

### Key Takeaways
- **Tool poisoning hides in metadata**: the danger lives in tool *descriptions*, not in the data a server holds.
- **Scanning is a supply-chain control**: vet MCP servers before an agent ever connects.
- **The taxonomy is the triage**: Direct Prompt Injection + Data Exfiltration via Agent Tooling name the attack precisely.
- **Layered engines beat any single one**: YARA for speed and determinism, LLM/API for semantic reach.

### Security Considerations
While the MCP Scanner is a powerful gate, remember to:
- Treat a SAFE result as *lower risk*, not *proven safe* — static and LLM detection both have blind spots.
- Keep engines layered and rules updated; attackers reword payloads to dodge signatures.
- Never point scanners or agents at servers holding *real* secrets during a lab — use test data only.
- Combine detection with runtime least-privilege and egress controls; scanning is defense-in-depth, not a silver bullet.
- Mind that the LLM and Cisco AI Defense engines make external API calls (latency, cost, and your data leaving the box) — scope keys and models accordingly.
