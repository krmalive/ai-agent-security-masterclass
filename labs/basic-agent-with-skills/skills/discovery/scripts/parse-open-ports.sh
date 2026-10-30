#!/usr/bin/env bash
set -euo pipefail

# Extract the open TCP/UDP ports from an nmap normal-output (-oN) file and print
# them as a single comma-separated list, e.g. "21,22,23,80,445".
#
# Why this exists: the nmap port table varies (column spacing, the VERSION column
# appearing only after -sV, states like "open|filtered"), so ad-hoc grep/cut
# pipelines silently miss ports. This parser keys off the structured first column
# (PORT in the form <number>/<proto>) and the STATE column, which is reliable.
#
# Usage: parse-open-ports.sh <nmap-normal-output-file>

FILE="${1:?usage: parse-open-ports.sh <nmap-normal-output-file>}"

if [ ! -f "$FILE" ]; then
  # No file means no discovery output; emit nothing so callers see an empty list.
  exit 0
fi

# Match lines that begin with "<port>/<tcp|udp>" and whose state field contains
# "open" (covers both "open" and "open|filtered"). Print just the port number.
awk '
  /^[0-9]+\/(tcp|udp)/ {
    state = $2
    if (state ~ /open/) {
      split($1, parts, "/")
      print parts[1]
    }
  }
' "$FILE" | paste -sd, -
