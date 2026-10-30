#!/usr/bin/env bash
# Shared nmap execution helper used by skill wrapper scripts.
#
# Reads scan runtime configuration from the environment so skills stay target-
# and deployment-agnostic. The harness or operator sets these before the agent runs:
#
#   NMAP_DOCKER_NETWORK  - When set, run nmap inside Docker attached to this network.
#   NMAP_DOCKER_IMAGE    - Scanner image (default: instrumentisto/nmap).
#   NMAP_PORT_LIST       - Comma-separated ports for discovery portscan phase.
#
# If NMAP_DOCKER_NETWORK is unset, nmap runs directly on the host (must be in PATH
# and able to reach the target).

run_nmap() {
  local output_dir="${1:?output directory required}"
  shift
  local -a nmap_args=("$@")

  if [ -n "${NMAP_DOCKER_NETWORK:-}" ]; then
    local image="${NMAP_DOCKER_IMAGE:-instrumentisto/nmap}"
    {
      echo "[nmap-run] mode=docker network=$NMAP_DOCKER_NETWORK image=$image"
      echo "[nmap-run] docker run --rm --network $NMAP_DOCKER_NETWORK -v $output_dir:$output_dir $image ${nmap_args[*]}"
    } >&2
    docker run --rm --network "$NMAP_DOCKER_NETWORK" \
      -v "$output_dir:$output_dir" \
      "$image" \
      "${nmap_args[@]}"
  else
    {
      echo "[nmap-run] mode=host"
      echo "[nmap-run] nmap ${nmap_args[*]}"
    } >&2
    nmap "${nmap_args[@]}"
  fi
}

require_port_list() {
  local ports="${NMAP_PORT_LIST:-}"
  if [ -z "$ports" ]; then
    echo "error: portscan requires NMAP_PORT_LIST (comma-separated ports). Set it in the environment or system message before running." >&2
    exit 1
  fi
  printf '%s' "$ports"
}
