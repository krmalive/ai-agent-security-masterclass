#!/usr/bin/env bash
# Demo 1 -- Authentication & Access Control, using raw curl (no LLM needed).
#
# Shows that the gateway verifies every token against the custom auth-server
# and only exposes the tools each user is authorized for.
set -euo pipefail

GW="http://localhost:8080/mcp"

list_tools () {  # $1 = token, $2 = label
  echo
  echo "### $2  (token: ${1:-<none>})"
  if [ -z "${1:-}" ]; then
    curl -s -X POST "$GW" \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
      -w "\n[HTTP %{http_code}]\n"
  else
    curl -s -X POST "$GW" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $1" \
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
      -w "\n[HTTP %{http_code}]\n"
  fi
}

echo "=== 1a. No token -> rejected (401) ==="
list_tools "" "No credentials"

echo
echo "=== 1b. Revoked token -> rejected (401) ==="
list_tools "tok_revoked_004" "Revoked user Mallory"

echo
echo "=== 1c. Alice (weather-user) -> only weather tools ==="
list_tools "tok_alice_weather_001" "Alice"

echo
echo "=== 1d. Bob (notes-user) -> only notes tools ==="
list_tools "tok_bob_notes_002" "Bob"

echo
echo "=== 1e. Admin -> everything ==="
list_tools "tok_admin_003" "Admin"

echo
echo "=== 1f. Alice tries to CALL a tool she is NOT authorized for (list_notes) -> 403 ==="
curl -s -X POST "$GW" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer tok_alice_weather_001" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_notes","arguments":{}}}' \
  -w "\n[HTTP %{http_code}]\n"
