#!/usr/bin/env bash
set -euo pipefail

# Summarize an nmap NSE "vuln" scan (normal -oN output) into a compact, greppable
# digest so the agent can turn it into structured vulnerability findings without
# re-reading the entire raw file.
#
# For each open port with NSE script output, it prints blocks like:
#
#   PORT 21/tcp ftp vsftpd 2.3.4
#     SCRIPT ftp-vsftpd-backdoor
#     STATE VULNERABLE
#     CVE CVE-2011-2523
#
# STATE is one of: VULNERABLE, LIKELY-VULNERABLE, NOT-VULNERABLE, UNKNOWN — inferred
# from the NSE output lines. The agent should still read nmap-vuln.txt for full
# evidence, but this digest makes the important signals easy to see.
#
# Usage: parse-vuln-output.sh <nmap-vuln.txt>

FILE="${1:?usage: parse-vuln-output.sh <nmap-vuln-output-file>}"

if [ ! -f "$FILE" ]; then
  exit 0
fi

awk '
  function flush_script() {
    if (script != "") {
      state = "UNKNOWN"
      if (seen_vulnerable) state = "VULNERABLE"
      else if (seen_likely) state = "LIKELY-VULNERABLE"
      else if (seen_notvuln) state = "NOT-VULNERABLE"
      printf "  SCRIPT %s\n", script
      printf "    STATE %s\n", state
      if (cve != "") printf "    CVE %s\n", cve
    }
    script = ""; cve = ""
    seen_vulnerable = 0; seen_likely = 0; seen_notvuln = 0
  }

  # Port header line, e.g. "21/tcp open ftp vsftpd 2.3.4"
  /^[0-9]+\/(tcp|udp)/ {
    flush_script()
    printf "PORT %s %s %s", $1, $2, $3
    $1=""; $2=""; $3=""
    rest = $0
    gsub(/^[ \t]+/, "", rest)
    if (rest != "") printf " %s", rest
    printf "\n"
    next
  }

  # NSE script id line. nmap prints the first line of multi-line script output as
  # "| <id>:" (pipe, single space, id) and single-line output as "|_<id>:" (pipe,
  # underscore, id directly). Continuation lines use "|" + 2+ spaces or "|_" + spaces,
  # so we require a non-space right after "| " or "|_".
  /^\| [^ ]/ || /^\|_[^ ]/ {
    flush_script()
    line = $0
    sub(/^\|_?[ ]?/, "", line)
    sub(/:.*$/, "", line)
    gsub(/^[ \t]+|[ \t]+$/, "", line)
    script = line
    next
  }

  {
    up = toupper($0)
    if (up ~ /VULNERABLE/ && up !~ /NOT VULNERABLE/) seen_vulnerable = 1
    if (up ~ /NOT VULNERABLE/) seen_notvuln = 1
    if (up ~ /LIKELY VULNERABLE/) seen_likely = 1
    # Capture the first CVE token seen within the current script block.
    if (cve == "" && match($0, /CVE-[0-9]{4}-[0-9]+/)) {
      cve = substr($0, RSTART, RLENGTH)
    }
  }

  END { flush_script() }
' "$FILE"
