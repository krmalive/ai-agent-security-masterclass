#!/usr/bin/env bash
set -euo pipefail

# Vulnerability-analysis nmap wrapper. Runs NSE --script vuln against open ports
# discovered in stage 1.
#
# Usage: nmap-vuln.sh <output-dir> <target> [ports]
#
# If [ports] is omitted, derives open ports from nmap-portscan.txt in output-dir.
# Output: nmap-vuln.txt (normal -oN format).
#
# Runtime configuration: NMAP_DOCKER_NETWORK, NMAP_DOCKER_IMAGE (see nmap-run.sh).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON_DIR="$(cd "$SCRIPT_DIR/../../common/scripts" && pwd)"
# shellcheck source=../../common/scripts/nmap-run.sh
source "$COMMON_DIR/nmap-run.sh"

OUTPUT_DIR="${1:?output directory required}"
TARGET="${2:?target required}"
PORTS="${3:-}"

mkdir -p "$OUTPUT_DIR"

if [ -z "$PORTS" ]; then
  PORTSCAN_FILE="$OUTPUT_DIR/nmap-portscan.txt"
  PARSER="$SCRIPT_DIR/../../discovery/scripts/parse-open-ports.sh"
  if [ -f "$PORTSCAN_FILE" ] && [ -f "$PARSER" ]; then
    PORTS="$(bash "$PARSER" "$PORTSCAN_FILE")"
  fi
fi

if [ -z "$PORTS" ]; then
  echo "error: no ports given and none found in $OUTPUT_DIR/nmap-portscan.txt" >&2
  exit 1
fi

OUTPUT_FILE="$OUTPUT_DIR/nmap-vuln.txt"
NMAP_ARGS=(-sT -Pn -T4 -sV --script vuln --script-timeout 120s -p "$PORTS" "$TARGET" -oN "$OUTPUT_FILE")

{
  echo "[nmap-vuln] target=$TARGET ports=$PORTS"
} >&2

run_nmap "$OUTPUT_DIR" "${NMAP_ARGS[@]}"
echo "$OUTPUT_FILE"
