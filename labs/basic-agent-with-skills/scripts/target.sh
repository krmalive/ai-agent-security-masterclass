#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"

TARGET_HOST="metasploitable"
SCAN_NETWORK="basic-agent-skill-scan-lab"

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    echo "error: neither 'docker compose' nor 'docker-compose' found" >&2
    exit 1
  fi
}

run_nmap() {
  docker run --rm --network "$SCAN_NETWORK" instrumentisto/nmap "$@"
}

cmd="${1:-ip}"

case "$cmd" in
  up)
    compose -f "$COMPOSE_FILE" up -d
    echo "Waiting for Metasploitable services to start (this can take up to a minute)..."
    for _ in $(seq 1 12); do
      if run_nmap -sT -Pn -p 22 "$TARGET_HOST" 2>/dev/null | grep -q "open"; then
        echo "Target ready at $TARGET_HOST on network $SCAN_NETWORK"
        exit 0
      fi
      sleep 5
    done
    echo "Container is up; SSH may still be starting. Scan target:"
    echo "$TARGET_HOST"
    ;;
  down)
    compose -f "$COMPOSE_FILE" down
    ;;
  ip)
    docker ps --format '{{.Names}}' | grep -qx metasploitable || {
      echo "error: metasploitable container not running. Run: npm run target:up" >&2
      exit 1
    }
    echo "$TARGET_HOST"
    ;;
  *)
    echo "Usage: $0 {up|down|ip}" >&2
    exit 1
    ;;
esac
