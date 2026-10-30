# Vulnerability Analysis Reference (service → NSE script → CVE)

This is a **method** for turning a discovered service into an evidence-backed vulnerability finding,
plus well-known examples to illustrate the pattern. It is **not** a checklist of what your target runs.
Only report a vulnerability when your `nmap-vuln.txt` output actually shows a `VULNERABLE` /
`LIKELY VULNERABLE` state (or a clearly outdated version with a known CVE, rated conservatively).

Match by **service name and version string** from discovery, not by port number alone. A database on a
non-standard port is still a database; an FTP daemon on 2121 is still FTP.

## The workflow

1. For each open port, take the `service` and `version` from discovery.
2. Find candidate NSE scripts for that service class (see "Finding the right scripts" below).
3. Read what actually fired in `nmap-vuln.txt` (use the `parse-vuln-output.sh` digest as an index).
4. If the state is `VULNERABLE`/`LIKELY VULNERABLE`, write a finding: quote the evidence, copy any CVE
   verbatim, and set severity per the rubric in `nse-vuln-reference.md`.
5. If a service is clearly outdated and maps to a well-known CVE but NSE did not confirm it, you may
   record it as **version-based** at `medium` at most — say so explicitly.

## Finding the right scripts (don't rely on memory)

NSE ships hundreds of scripts named `<service>-<check>`. Discover them instead of guessing:

```bash
nmap --script-help "ftp-*"        # list + describe all FTP scripts
nmap --script-help "smb-vuln-*"   # all SMB vuln scripts
ls /usr/share/nmap/scripts/ | grep -i mysql
```

The `nmap-vuln.sh` wrapper already runs the whole `vuln` category with `-sV`, so version-matched vuln
scripts fire automatically. Your job is to **read and interpret** what fired, using the naming
convention to know which service each result belongs to.

## Reasoning by service class

Think in classes, then let the version string narrow it down. These are common patterns and famous
examples — treat the examples as *illustrations of the class*, not as predictions about your target.

### File transfer (FTP, TFTP, NFS)
- Look for: anonymous access, backdoored builds, path traversal, use-after-free in specific versions.
- Script families: `ftp-anon`, `ftp-*-backdoor`, `ftp-vuln-*`, `tftp-*`, `nfs-*`.
- Classic example: some vsftpd builds shipped a command backdoor (CVE-2011-2523) — `ftp-vsftpd-backdoor`
  reporting `VULNERABLE` is high severity. Anonymous login (`ftp-anon`) is a config finding.

### SMB / file sharing (Samba, Windows SMB)
- Look for: RCE in the negotiation/parsing path, command injection in config options, legacy SMBv1.
- Script families: `smb-vuln-*`, `smb-os-discovery`, `smb-enum-*`.
- Classic examples: Samba `username map script` command injection (CVE-2007-2447); Windows MS08-067
  (CVE-2008-4250) and MS17-010 / EternalBlue (CVE-2017-0143). Read the `State:` line carefully — some
  `smb-vuln-*` scripts are safe-check only.

### Remote access (SSH, Telnet, RDP, VNC, r-services)
- Look for: cleartext protocols, weak/legacy auth, version-specific CVEs, trust relationships
  (`.rhosts` on rsh/rlogin).
- Script families: `ssh2-enum-algos`, `ssh-*`, `rdp-vuln-*`, `vnc-*`, `rlogin-*`.
- Cleartext management (telnet, rlogin, rsh) is itself a weakness worth noting even without a CVE.

### Web / application servers (Apache, nginx, IIS, Tomcat, AJP)
- Look for: outdated server CVEs, exposed admin/manager apps, default credentials, protocol smuggling.
- Script families: `http-vuln-*`, `http-enum`, `http-default-accounts`, `http-slowloris-check`, `ajp-*`.
- Examples: old Apache 2.2.x has many version-dependent CVEs (trust the NSE state, not just the
  version); AJP connectors are exposed to Ghostcat (CVE-2020-1938). Default app-manager credentials are
  usually an exploitation-stage concern.

### Databases (MySQL/MariaDB, PostgreSQL, MSSQL, MongoDB, Redis)
- Look for: empty/default passwords, auth bypass, network exposure of an admin interface.
- Script families: `mysql-*`, `ms-sql-*`, `mongodb-*`, `redis-info`.
- Examples: empty root password (`mysql-empty-password`) is high; MySQL auth bypass CVE-2012-2122
  (`mysql-vuln-cve2012-2122`). Any internet-exposed DB admin port is worth noting.

### Mail / DNS / RPC / middleware
- Look for: version CVEs, open relays, zone transfer, exposed RPC services, distributed-compute daemons.
- Script families: `smtp-*`, `dns-*` (e.g. `dns-zone-transfer`), `rpcinfo`, `distcc-*`, `java-rmi-*`.
- Example: a distcc daemon accepting untrusted connections allows remote command execution
  (CVE-2004-2687, `distcc-cve2004-2687`).

### Chat / other network daemons (IRC, etc.)
- Look for: trojaned/backdoored builds, version CVEs.
- Example: some UnrealIRCd tarballs were trojaned with a command backdoor (CVE-2010-2075,
  `irc-unrealircd-backdoor`).

### TLS / crypto (any service wrapped in SSL/TLS)
- Look for: weak protocols/ciphers, known TLS attacks. Usually low–medium.
- Script families: `ssl-enum-ciphers`, `ssl-poodle`, `ssl-dh-params`, `ssl-heartbleed`.

### Unknown / suspicious listeners
- A `open` port with no recognizable service, or a raw shell banner on an odd port, may be a backdoor
  listener. Record the banner verbatim and flag it `unknown`/high for the exploitation stage to confirm
  — do not invent a CVE.

## Severity (summary — full rubric in nse-vuln-reference.md)

- **high** — `VULNERABLE (Exploitable)`, RCE, backdoors, confirmed unauthenticated shell/DB access.
- **medium** — `VULNERABLE` (not exploitable) / `LIKELY VULNERABLE`; outdated service + known CVE, no
  confirmed path; information disclosure / weak config.
- **low** — informational weakness (e.g. weak TLS ciphers) with no directly usable path.

## Evidence discipline

- No `VULNERABLE`/`LIKELY VULNERABLE` state and no clear outdated-version+CVE mapping = **no finding**.
- Copy CVEs and version strings verbatim from the actual output.
- Version-only findings (no NSE confirmation) are `medium` at most and must be labeled version-based.
- Prefer fewer, well-evidenced findings over many speculative ones.
