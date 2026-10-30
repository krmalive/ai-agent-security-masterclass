#!/usr/bin/env bash
set -euo pipefail

# Discovery-stage nmap wrapper. Runs a two-phase discovery workflow against one
# authorized target: portscan, then service/version detection on open ports only.
#
# Usage: nmap-discovery.sh <output-dir> <target> <portscan|services> [ports]
#
# Phases:
#   portscan  - TCP connect scan over NMAP_PORT_LIST -> nmap-portscan.txt
#   services  - -sV on given ports (or auto-derived from portscan) -> nmap-services.txt
#
# Runtime configuration (environment — set by harness or operator):
#   NMAP_DOCKER_NETWORK, NMAP_DOCKER_IMAGE, NMAP_PORT_LIST
# See skills/common/scripts/nmap-run.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON_DIR="$(cd "$SCRIPT_DIR/../../common/scripts" && pwd)"
# shellcheck source=../../common/scripts/nmap-run.sh
source "$COMMON_DIR/nmap-run.sh"

OUTPUT_DIR="${1:?output directory required}"
TARGET="${2:?target required}"
RAW_PHASE="${3:?phase required: portscan or services}"

mkdir -p "$OUTPUT_DIR"

case "$(printf '%s' "$RAW_PHASE" | tr '[:upper:]' '[:lower:]')" in
  portscan|ports|discovery|discover|scan) PHASE="portscan" ;;
  services|service|service-detect|service_detect|service-detection|service_version|serviceversion|sv|version|versions) PHASE="services" ;;
  *) echo "error: unknown phase '$RAW_PHASE' (use 'portscan' or 'services')" >&2; exit 1 ;;
esac

case "$PHASE" in
  portscan)
    PORTS="$(require_port_list)"
    OUTPUT_FILE="$OUTPUT_DIR/nmap-portscan.txt"
    EXTRA_ARGS=(-T4)
    ;;
  services)
    PORTS="${4:-}"
    if [ -z "$PORTS" ]; then
      PORTSCAN_FILE="$OUTPUT_DIR/nmap-portscan.txt"
      if [ -f "$PORTSCAN_FILE" ]; then
        PORTS="$(bash "$SCRIPT_DIR/parse-open-ports.sh" "$PORTSCAN_FILE")"
      fi
    fi
    if [ -z "$PORTS" ]; then
      echo "error: services phase needs open ports (pass as 4th arg or run portscan first)" >&2
      exit 1
    fi
    OUTPUT_FILE="$OUTPUT_DIR/nmap-services.txt"
    EXTRA_ARGS=(-T4 -sV)
    ;;
esac

NMAP_ARGS=(-sT -Pn "${EXTRA_ARGS[@]}" -p "$PORTS" "$TARGET" -oN "$OUTPUT_FILE")

{
  echo "[nmap-discovery] phase=$PHASE target=$TARGET ports=$PORTS"
} >&2

run_nmap "$OUTPUT_DIR" "${NMAP_ARGS[@]}"
echo "$OUTPUT_FILE"
