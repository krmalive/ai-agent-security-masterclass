# Service Identification Catalog

Use this to interpret what a discovered service is and why it is interesting, so the discovery
report's `open_ports` notes are accurate. Match by **service name and version string** from your
`-sV` output — not by assuming fixed ports. A database on a non-standard port is still a database.

This catalog is for *identification and context only*. Do not assign vulnerability severities or
claim exploitability here — that is the job of the later vulnerability-analysis and exploitation
stages. Keep discovery notes short and factual (e.g. "anonymous login banner seen", "very old
version string").

## How to use

For each open port in your scan, find the matching service category below and record:

- the port number and protocol,
- the nmap service name (lowercase),
- the version string verbatim (or omit if blank/uncertain),
- an optional short `notes` field with a factual observation from the banner.

## Service categories

### Remote access and management

| Service (nmap name) | Typical ports | What it is | What to note in discovery |
|---------------------|---------------|------------|---------------------------|
| telnet | 23 | Cleartext remote shell/management. | Version banner; that it is cleartext. |
| ssh | 22 | Encrypted remote shell. | Exact OpenSSH version (useful for later CVE mapping). |
| vnc | 5900+ | Remote desktop. | Version; whether a banner hints at auth. |
| rlogin / login | 513 | Cleartext BSD remote login. | Presence; trusts `.rhosts`. |
| rsh / shell | 514 | Cleartext BSD remote shell. | Presence. |
| rexec / exec | 512 | Cleartext remote command execution. | Presence. |

### File transfer

| Service | Typical ports | What it is | What to note in discovery |
|---------|---------------|------------|---------------------------|
| ftp (vsftpd, ProFTPD, etc.) | 21, 2121 | File transfer, often cleartext. | Product + version; anonymous-login banner if shown. |
| tftp | 69 (UDP) | Trivial FTP, often unauthenticated. | Presence. |
| nfs | 2049 | Network file shares. | Presence; version. |
| netbios-ssn / microsoft-ds / smb | 139, 445 | Windows/Samba file sharing. | Samba version string if present. |

### Web and application servers

| Service | Typical ports | What it is | What to note in discovery |
|---------|---------------|------------|---------------------------|
| http / ssl/http / https | 80, 443, 8080, 8180, 8443 | Web/app servers. | Server product + version (Apache, nginx, Tomcat, IIS). |
| ajp13 | 8009 | Apache JServ Protocol connector. | Presence; often fronts Tomcat. |
| java-rmi / grmiregistry | 1099 | Java RMI registry. | Presence; version. |

### Databases and data stores

| Service | Typical ports | What it is | What to note in discovery |
|---------|---------------|------------|---------------------------|
| mysql / mariadb | 3306 | Relational DB. | Version; that it is network-exposed. |
| postgresql | 5432 | Relational DB. | Version. |
| mongodb | 27017 | Document DB. | Version. |
| redis | 6379 | In-memory data store. | Version. |
| mssql / ms-sql-s | 1433 | Enterprise DB. | Version. |

### Mail, DNS, RPC, middleware, and misc

| Service | Typical ports | What it is | What to note in discovery |
|---------|---------------|------------|---------------------------|
| smtp / postfix / exim | 25, 587 | Mail transfer agent. | Product + version. |
| domain / bind | 53 | DNS server. | BIND version if shown. |
| rpcbind | 111 | RPC portmapper. | Presence. |
| distccd | 3632 | Distributed C compiler daemon. | Presence + version (notable if exposed). |
| drb (Ruby DRb) | 8787+ | Ruby distributed objects. | Presence. |
| irc / unrealircd | 6667, 6697 | IRC daemon. | Product + version. |
| X11 | 6000+ | X display server over TCP. | Presence; whether access is denied. |

### Suspicious or unknown listeners

| Pattern | What to note in discovery |
|---------|---------------------------|
| `open` port with no recognizable service, or names like `shell`, `backdoor`, `ingreslock` (1524) | Record the raw banner verbatim; flag as unknown for later stages to investigate. |
| `tcpwrapped` | Connection reached a TCP wrapper; service identity unclear. Note verbatim; don't invent a product. |
| `service?` or trailing `?` | nmap uncertain — record uncertainty; don't upgrade to a confident identification. |

## Evidence discipline

- Only record ports whose state is `open` (or `open|filtered`).
- Copy version strings verbatim; omit rather than guess.
- Keep `notes` factual and short. Risk rating and exploitability belong to later stages.
