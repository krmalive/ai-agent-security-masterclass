# Nmap Reference

Condensed, practical nmap knowledge distilled from the official *Nmap Network Scanning* book by Gordon
"Fyodor" Lyon (<https://nmap.org/book/>). Use this to interpret scan output correctly and to understand
*why* constrained scan environments use the options they do. When running through `nmap-discovery.sh`
you use the unprivileged TCP connect workflow; the rest of this doc is background that makes you a
better analyst, not a list of commands to run blindly.

## Contents

1. [The phases of an nmap scan](#1-the-phases-of-an-nmap-scan)
2. [Port states](#2-port-states)
3. [Host discovery (ping scanning)](#3-host-discovery-ping-scanning)
4. [Port scanning techniques](#4-port-scanning-techniques)
5. [Service and version detection (-sV)](#5-service-and-version-detection--sv)
6. [OS detection (-O)](#6-os-detection--o)
7. [The Nmap Scripting Engine (NSE)](#7-the-nmap-scripting-engine-nse)
8. [Timing and performance (-T)](#8-timing-and-performance--t)
9. [Firewall / IDS evasion](#9-firewall--ids-evasion)
10. [Output formats](#10-output-formats)
11. [Why constrained environments use -sT -Pn](#11-why-constrained-environments-use--st--pn)

---

## 1. The phases of an nmap scan

A typical nmap invocation moves through these phases, each of which can be tuned or skipped:

1. **Target enumeration** — expand the targets (hostnames, CIDR ranges, lists) into IP addresses.
2. **Host discovery (ping scan)** — decide which targets are up before spending effort on them. Skip
   with `-Pn` (treat all hosts as up) or do only this with `-sn` (no port scan).
3. **Reverse-DNS resolution** — look up names for the live IPs (`-n` disables, `-R` forces).
4. **Port scanning** — probe ports and classify their state.
5. **Version detection** (`-sV`) — interrogate open ports to identify the service and version.
6. **OS detection** (`-O`) — fingerprint the TCP/IP stack to guess the operating system.
7. **Traceroute** (`--traceroute`).
8. **Script scanning** (NSE, `-sC`/`--script`).
9. **Output** — write results in the chosen formats.

The two-phase workflow (discovery, then service detection on open ports only) keeps the trace easy to
follow and avoids wasting `-sV` time on closed ports.

## 2. Port states

Nmap reports six states. They describe *what nmap can tell*, not an intrinsic property of the port:

- **open** — an application is actively accepting connections. This is the attack surface you care
  about most.
- **closed** — reachable, but nothing is listening. Useful for confirming a host is up.
- **filtered** — nmap can't tell if it's open because a firewall/filter dropped the probe. These slow
  scans down because nmap retries.
- **unfiltered** — reachable but open/closed is undetermined (only the ACK scan produces this).
- **open|filtered** — nmap can't decide between open and filtered (common with UDP, NULL/FIN/Xmas
  scans, where open ports give no response). Treat these as "possibly open."
- **closed|filtered** — only from the IP ID idle scan.

For the report, count `open` (and `open|filtered`) ports as the live surface.

## 3. Host discovery (ping scanning)

Before port scanning, nmap tries to confirm a host is up to avoid wasting time on dead IPs. Techniques:

- `-sL` (list scan) — just list/resolve targets, no packets to hosts.
- `-sn` — host discovery only, no port scan.
- `-Pn` — **skip discovery; assume the host is up.** Essential when ICMP and probe ports are filtered
  (common when ICMP or probe ports are filtered so the scan isn't aborted by a failed ping).
- Probe types: `-PS<ports>` (TCP SYN ping), `-PA<ports>` (TCP ACK ping), `-PU<ports>` (UDP ping),
  `-PE/-PP/-PM` (ICMP echo/timestamp/netmask), `-PO` (IP protocol ping), `-PR` (ARP ping, default on a
  local Ethernet segment and very reliable).

## 4. Port scanning techniques

Only one TCP technique is used at a time. **Most require root** (raw packets); unprivileged users can
only run connect (`-sT`) and FTP bounce (`-b`).

- **`-sS` (SYN / half-open)** — the default when privileged. Sends SYN, waits: SYN/ACK = open, RST =
  closed, no response (after retries) = filtered. Fast, relatively stealthy, never completes the
  handshake. Needs root.
- **`-sT` (TCP connect)** — used when SYN isn't available (no raw-packet privilege). Asks the OS to
  fully `connect()`. No root needed, but slower and more likely to be logged by the target. **This is
  what unprivileged/sandbox scans use.**
- **`-sU` (UDP)** — probes UDP ports; open ports often stay silent → `open|filtered`. Slow due to ICMP
  rate limiting. Needs root. Pair with `-sV` to confirm truly-open UDP ports.
- **`-sN` / `-sF` / `-sX` (NULL / FIN / Xmas)** — set no flags / FIN / FIN+PSH+URG. Closed ports return
  RST, open ports stay silent → `open|filtered`. Can slip past non-stateful filters but unreliable
  against Windows/Cisco (which RST everything). Need root.
- **`-sA` (ACK)** — maps firewall rules; never finds open ports, only `filtered` vs `unfiltered`.
- **`-sW` (Window)**, **`-sM` (Maimon)** — niche variants exploiting stack quirks.
- **`-sO` (IP protocol scan)** — which IP protocols (TCP/ICMP/IGMP…) the host supports.
- **`-sI` (idle scan)** — blind scan bounced off a "zombie" host; extremely stealthy.
- **`-b` (FTP bounce)** — abuse proxy-FTP to scan through an FTP server (mostly historical).

## 5. Service and version detection (-sV)

`-sV` connects to each open port and matches responses against the `nmap-service-probes` database to
report the actual service and version (e.g., `Apache httpd 2.2.8 ((Ubuntu) DAV/2)`). Notes:

- `--version-intensity <0-9>` controls how many probes are tried (higher = more accurate, slower).
  `--version-light` = intensity 2; `--version-all` = intensity 9.
- Output you may see and how to treat it:
  - A clear product/version string → record it in `version`.
  - `tcpwrapped` → the TCP handshake completed but the service dropped the connection (often a wrapper
    like tcpd). Record verbatim or omit; don't invent a product.
  - `service?` or a trailing `?` → nmap is unsure of the service. Don't upgrade a guess into a fact.
  - Empty VERSION column → no version was determined; omit `version`.
- `-sV` is what turns a bare open port into credible evidence for a finding. Run it only on ports
  confirmed open by discovery — not on the full port list.

## 6. OS detection (-O)

`-O` sends a series of TCP/IP probes and compares the responses against `nmap-os-db` to guess the OS.
It **requires root** (raw sockets) and is unavailable in unprivileged/sandbox environments.
`--osscan-guess` makes nmap report near-matches when a fingerprint is close. Useful for inventory,
exploit tailoring, and spotting rogue devices.

## 7. The Nmap Scripting Engine (NSE)

NSE runs Lua scripts for richer discovery, version detection, vuln checks, and more.

- `-sC` runs the **default** script set; `--script <name|category|pattern>` runs specific ones;
  `--script-args` passes parameters.
- Categories include `safe`, `default`, `discovery`, `version`, `auth`, `brute`, `vuln`, `exploit`,
  `intrusive`, `dos`, `malware`. `safe`/`default`/`discovery` are low-risk; `intrusive`, `brute`,
  `exploit`, `dos` can disrupt the target — don't run them casually.
- Connect-style NSE scripts don't need root, but they add time and noise. In the discovery stage,
  stick to `-sV` for service identification; NSE vuln/exploit scripts belong to the later pipeline
  stages.

## 8. Timing and performance (-T)

Timing templates trade speed for stealth/reliability:

- `-T0` paranoid, `-T1` sneaky, `-T2` polite, `-T3` normal (default), `-T4` aggressive, `-T5` insane.
- `-T4` (aggressive) is typical for fast scans on local or trusted networks.
- Fine controls exist (`--min-rate`, `--max-rate`, `--max-retries`, `--host-timeout`, `--scan-delay`),
  but you don't need them here.

## 9. Firewall / IDS evasion

Background only — use only when explicitly authorized and requested. Techniques include fragmentation (`-f`, `--mtu`), decoys
(`-D`), source-port spoofing (`--source-port`), idle scan (`-sI`), MAC spoofing (`--spoof-mac`), and
timing slow-downs. They exist to test whether filters and IDS rules actually hold.

## 10. Output formats

- `-oN <file>` — **normal** human-readable output (what the scan wrapper saves). The port table has columns
  `PORT  STATE  SERVICE  [VERSION]`.
- `-oG <file>` — grepable (one host per line; legacy but easy to `grep`/`awk`).
- `-oX <file>` — XML (best for programmatic parsing).
- `-oA <base>` — all three at once.
- Verbosity `-v`/`-vv`, debugging `-d`, packet trace `--packet-trace`.

Reading the normal port table is what matters here: take the port number from the `PORT` column (left
of the `/`), keep rows whose `STATE` contains `open`, and read `SERVICE`/`VERSION` for the rest.

## 11. Why constrained environments use -sT -Pn

- **`-sT`** — when raw-socket (root) privileges aren't available, SYN, UDP, NULL/FIN/Xmas, and OS
  detection aren't options. TCP connect is the correct unprivileged choice and gives reliable
  open/closed/filtered results.
- **`-Pn`** — skips host discovery so the scan proceeds even if ping probes are filtered — essential
  for containerized targets, firewalled hosts, or any environment where ICMP is blocked.
- **Scanner container / wrapper** — some targets are only reachable from a specific network namespace
  (e.g., a Docker network). Running through `nmap-discovery.sh` attaches the scanner to that network;
  a bare host-side `nmap` against the same hostname may fail with "host seems down."
