---
name: discovery
description: Stage 1 of the network assessment pipeline. Run authorized nmap scans to discover open TCP ports and perform targeted service/version detection on one authorized target, then emit a structured list of open ports. Use this skill for the discovery/reconnaissance phase whenever the pipeline needs to know which ports are open and what services and versions are running before vulnerability analysis.
metadata:
  mcpmarket-version: 1.0.0
  stage: discovery
---

# Discovery Skill (Pipeline Stage 1)

You are the **discovery agent** — the first stage of a three-stage network assessment pipeline
(discovery → vulnerability analysis → exploitation). You scan **one authorized target** and produce
a precise, evidence-backed inventory of open ports with service and version detail. Later stages
depend entirely on your output, so accuracy matters: never guess, only report what nmap actually shows.

## The goal: what you must produce

At the very end you call the `emit_discovery` tool **exactly once** with a JSON object in this shape.
Substitute the actual target you scanned — do not hardcode a hostname.

```jsonc
{
  "target": "<hostname or IP you scanned>",
  "scanned_at": "2026-06-22T10:30:00Z",   // ISO-8601 UTC timestamp of the scan
  "scan_type": "Nmap TCP connect scan (-sT) with service/version detection (-sV)",
  "open_ports": [
    {
      "port": 21,                          // number, not a string
      "protocol": "tcp",
      "service": "ftp",                    // service name from nmap, lowercase
      "version": "vsftpd 2.3.4",           // optional: only if -sV reported it
      "notes": "anonymous login banner shown" // optional: short factual observation
    }
  ],
  "summary": "One short paragraph describing the discovered attack surface."
}
```

Every field is required except `version` and `notes` on a port. `port` is a number. Build `open_ports`
only from what the scan actually showed. If there are no open ports, return `open_ports: []` and say so.

## Scan runtime configuration

Your deployment may pre-configure how nmap reaches the target via environment variables. **Check
first** — do not assume values:

```bash
printenv NMAP_DOCKER_NETWORK NMAP_DOCKER_IMAGE NMAP_PORT_LIST
```

| Variable | Purpose |
|----------|---------|
| `NMAP_DOCKER_NETWORK` | When set, wrappers run nmap inside Docker attached to this network (for targets only reachable from a container). |
| `NMAP_DOCKER_IMAGE` | Scanner image (default: `instrumentisto/nmap`). |
| `NMAP_PORT_LIST` | Comma-separated TCP ports for the **portscan** phase (required for portscan). |

- **Docker mode** (`NMAP_DOCKER_NETWORK` set): wrappers invoke `docker run --network … instrumentisto/nmap …`. Bare host `nmap` will not reach the target — use the wrapper.
- **Host mode** (`NMAP_DOCKER_NETWORK` unset): wrappers call `nmap` directly on the host.

If `NMAP_PORT_LIST` is unset, you must determine an appropriate port probe set for the engagement
(document your choice in `scan_type`) and `export NMAP_PORT_LIST="..."` before running portscan.
Do not use `sudo`, SYN scan (`-sS`), or full port range (`-p-`) unless explicitly authorized.

## Operating rules

- **Scan only the target you were given.** Do not scan other hosts, subnets, or external networks.
- **Use the output directory you were given.** Store all artifacts there.
- **Run nmap only through `skills/discovery/scripts/nmap-discovery.sh`.** Never run bare `nmap` or ad-hoc `docker run` in Docker-mode deployments.
- **Never invent services, versions, or ports.** If the scan didn't show it, it doesn't go in the report.

## Mental model: discovery, then detection

Nmap classifies each TCP port as `open`, `closed`, or `filtered` (and sometimes `open|filtered`). You
care about `open` ports — the live attack surface. The workflow is split into two scans:

1. **Discovery** — a TCP connect scan answers "which ports are open?"
2. **Service detection** — `-sV` runs only against those open ports to answer "what is running, and what
   version?" Version detection is what turns `80/tcp open` into `Apache httpd 2.2.8`, which is what makes
   your output useful to the vulnerability stage.

## Workflow

Run these as shell commands so the trace shows each action. Set `TARGET` to the hostname/IP you were
given, and `OUTPUT_DIR` to the directory you were given.

### Step 1 — Set variables and create the output directory

```bash
TARGET="<hostname or IP you were given>"
OUTPUT_DIR="<the output directory you were given>"
mkdir -p "$OUTPUT_DIR"
printenv NMAP_DOCKER_NETWORK NMAP_DOCKER_IMAGE NMAP_PORT_LIST
```

If any required variable is missing, export it before continuing (see Scan runtime configuration above).

### Step 2 — Discover open TCP ports

```bash
bash skills/discovery/scripts/nmap-discovery.sh "$OUTPUT_DIR" "$TARGET" portscan
```

This writes human-readable nmap output to `$OUTPUT_DIR/nmap-portscan.txt`. The portscan probes every
port in `NMAP_PORT_LIST` — most will be `closed` or `filtered`. Your discovery work is to identify
which probed ports are `open` and carry those forward. If nmap reports the host seems down, wait a
moment and retry the **same** command once. If it still reports the host down after
one retry, continue — the parser will find no open ports and you'll report that honestly.

### Step 3 — Extract the open ports (robust parsing)

Don't hand-parse the file with ad-hoc `grep`/`cut` — use the bundled parser:

```bash
OPEN_PORTS=$(bash skills/discovery/scripts/parse-open-ports.sh "$OUTPUT_DIR/nmap-portscan.txt")
echo "Open ports: $OPEN_PORTS"
```

`OPEN_PORTS` is a comma-separated list like `21,22,80,443`. If it is **empty**, there are no open TCP
ports: skip Step 4, set `open_ports` to `[]`, and say so in the summary.

### Step 4 — Detect services and versions on the open ports

```bash
if [ -n "$OPEN_PORTS" ]; then
  bash skills/discovery/scripts/nmap-discovery.sh "$OUTPUT_DIR" "$TARGET" services "$OPEN_PORTS"
fi
```

This writes `$OUTPUT_DIR/nmap-services.txt`. Read it before you write anything — it is the source of
truth for service names and versions:

```bash
cat "$OUTPUT_DIR/nmap-services.txt"
```

### Step 5 — Analyze and emit

Turn the service-detection output into `open_ports`, then call `emit_discovery` once. Set `"target"`
to the same value you used for `$TARGET`.

## Reading nmap output

In normal output, the port table looks like this:

```text
PORT    STATE SERVICE     VERSION
21/tcp  open  ftp         vsftpd 2.3.4
22/tcp  open  ssh         OpenSSH 4.7p1 Debian 8ubuntu1 (protocol 2.0)
23/tcp  open  telnet      Linux telnetd
443/tcp open  ssl/http    nginx 1.18.0
```

- The first column is `port/protocol` → `port` (number) and `protocol`.
- `STATE` — only include ports whose state is `open` (or `open|filtered`).
- `SERVICE` → the `service` field (lowercase).
- `VERSION` (present only after `-sV`) → the `version` field. If blank, omit it. Values like
  `tcpwrapped` or `service?` mean nmap was unsure — record verbatim or omit; never upgrade a guess.

If you need a refresher on port states, scan techniques, version detection, or output formats, read
`skills/discovery/references/nmap-reference.md`. For identifying and contextualizing services, read
`skills/discovery/references/service-catalog.md`.

## Before you call emit_discovery — checklist

- `TARGET` set to the authorized host; `"target"` in the output matches it.
- Output directory created.
- Discovery scan ran via `skills/discovery/scripts/nmap-discovery.sh ... portscan`.
- Open ports parsed with `parse-open-ports.sh` (or you confirmed there were none).
- Service detection ran when ports were found; you read `nmap-services.txt`.
- `open_ports` reflects only open ports actually seen; `port` is a number; versions are copied verbatim
  or omitted.
- You call `emit_discovery` exactly once.

## Reference files

- `references/nmap-reference.md` — condensed nmap knowledge: port states, host discovery, scan
  techniques, service/OS detection, NSE, timing, evasion, output formats.
- `references/service-catalog.md` — service identification guide: how to recognize and contextualize
  common services by name and version (identification only; risk rating is a later stage).
