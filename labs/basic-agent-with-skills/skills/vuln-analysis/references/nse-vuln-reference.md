# NSE Vulnerability Scanning Reference

How to run and read the Nmap Scripting Engine (NSE) `vuln` category, so the vulnerability-analysis
stage produces accurate, evidence-backed findings. Distilled from the official Nmap NSE documentation
(<https://nmap.org/book/nse.html>) and the `vuln` script library (<https://nmap.org/nsedoc/categories/vuln.html>).

## What NSE is

NSE runs Lua scripts that go beyond port/version detection: they actively interrogate a service to
check for known vulnerabilities, misconfigurations, and exposed information. Scripts are grouped into
categories; this stage uses the **`vuln`** category, which is designed to detect known vulnerabilities.

Invocation used by `nmap-vuln.sh`:

```text
nmap -sT -Pn -T4 -sV --script vuln --script-timeout 120s -p <open_ports> <target> -oN nmap-vuln.txt
```

- `-sV` gives scripts accurate service/version context (many `vuln` scripts only fire on a matched
  service).
- `--script vuln` runs the whole vuln category.
- `--script-timeout 120s` bounds any single slow script so the pipeline can't hang.

## Reading NSE output

NSE output is attached under each port in the normal (`-oN`) report. A script's output begins with a
line like `| <script-id>:` and continues on `|` continuation lines, ending with `|_`.

The `vuln` library uses a standard `vulns` output format. Learn to recognize these states:

```text
| ftp-vsftpd-backdoor:
|   VULNERABLE:
|   vsFTPd version 2.3.4 backdoor
|     State: VULNERABLE (Exploitable)
|     IDs:  CVE:CVE-2011-2523
|     ...
|_    Disclosure date: 2011-07-03
```

- **`State: VULNERABLE`** or **`VULNERABLE (Exploitable)`** — nmap positively detected the issue. This
  is your strongest evidence. `(Exploitable)` means NSE believes it can be exploited.
- **`State: LIKELY VULNERABLE`** — probable but not confirmed (e.g. matched by version only).
- **`State: NOT VULNERABLE`** — the check ran and the target is not affected. Do **not** report these.
- **`State: UNKNOWN`** or no state line — the script could not determine the state. Treat as
  informational; do not claim a vulnerability.

## CVE and identifier lines

Scripts often include identifiers under an `IDs:` line, e.g. `IDs: CVE:CVE-2011-2523` or
`BID:48539`. Copy the CVE **verbatim** into your finding's `cve` field. Never invent or guess a CVE
number — only record one that appears in the actual NSE output.

## Severity mapping for this stage

NSE does not always print a CVSS score. Map to `high` / `medium` / `low` using this rubric, and always
tie the rating to the evidence line you saw:

- **high** — `State: VULNERABLE (Exploitable)`, remote code execution, backdoors, cleartext admin
  access confirmed exploitable, unauthenticated access to a shell/DB.
- **medium** — `State: VULNERABLE` without `(Exploitable)`, or `LIKELY VULNERABLE`; information
  disclosure, weak configuration, outdated service with a known CVE but no confirmed exploit path.
- **low** — informational script output (e.g. supported ciphers, banners) that indicates weakness but
  not a directly usable vulnerability.

## Evidence discipline

- Report a vulnerability only if the NSE output shows `VULNERABLE` or `LIKELY VULNERABLE` for that
  script, or if a clearly outdated version maps to a well-known CVE (record it as `medium` and note it
  is version-based, not exploit-confirmed).
- Quote the actual line(s) from `nmap-vuln.txt` as `evidence`.
- Record the exact NSE `script id` in `nse_script` (e.g. `ftp-vsftpd-backdoor`, `smb-vuln-ms08-067`).
- Prefer fewer, well-evidenced findings over many speculative ones. `NOT VULNERABLE` and `UNKNOWN`
  results are not findings.

## Script families you may see (by service class)

NSE scripts are named `<service>-<check>`, which tells you which service a result belongs to. These are
common families, not a checklist for any particular target:

| Family | Targets | Signals |
|--------|---------|---------|
| `ftp-*` (e.g. `ftp-anon`, `ftp-*-backdoor`) | FTP | Anonymous access, backdoored builds. |
| `smb-vuln-*` | SMB / Samba / Windows | RCE and command-injection CVEs; some are safe-check only. |
| `http-vuln-*`, `http-enum`, `http-default-accounts` | Web / app servers | Version CVEs, exposed apps, default creds. |
| `mysql-*`, `ms-sql-*`, `mongodb-*` | Databases | Empty/default password and info-disclosure checks. |
| `ssl-*` (e.g. `ssl-poodle`, `ssl-dh-params`, `ssl-heartbleed`) | TLS services | Protocol/cipher weaknesses (often medium/low). |
| `smtp-*`, `dns-*`, `rpcinfo` | Mail / DNS / RPC | Open relay, zone transfer, exposed RPC services. |
| product-specific (e.g. `distcc-*`, `irc-*-backdoor`) | Misc daemons | Version/backdoor CVEs for that product. |

Discover the full set for a service with `nmap --script-help "<service>-*"`. Match the script to the
service you discovered, read its `State:` line, and only then write a finding.
