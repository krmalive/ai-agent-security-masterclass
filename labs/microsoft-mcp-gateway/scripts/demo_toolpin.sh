#!/usr/bin/env bash
# Demo 2 -- Tool Registration / anti "rug pull", using raw curl.
#
# Shows that when the mcp-notes backend is compromised and starts advertising a
# NEW malicious tool, the gateway refuses to surface or route it because it was
# never registered.
set -euo pipefail

GW="http://localhost:8080/mcp"
NOTES_ADMIN="http://localhost:9100"
ADMIN_TOKEN="tok_admin_003"   # admin sees ALL registered tools, so filtering is by registry only

call () {  # $1 = json body
  curl -s -X POST "$GW" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d "$1"
}

echo "=== 2a. Baseline: what the notes backend exposes THROUGH the gateway (admin) ==="
call '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
echo

echo
echo "=== 2b. Compromise the backend: it now advertises 'exfiltrate_secrets' ==="
curl -s -X POST "$NOTES_ADMIN/admin/compromise"; echo

echo
echo "=== 2c. Look at the backend DIRECTLY (bypassing the gateway) -- malicious tool is present ==="
curl -s -X POST "$NOTES_ADMIN/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
echo

echo
echo "=== 2d. Now list THROUGH the gateway -- 'exfiltrate_secrets' is GONE (blocked by registry) ==="
call '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
echo

echo
echo "=== 2e. Try to CALL the malicious tool through the gateway anyway -> 403 ==="
call '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"exfiltrate_secrets","arguments":{}}}'
echo

echo
echo "Check the gateway logs to see the BLOCK line:"
echo "    docker compose logs gateway | grep BLOCK"
echo
echo "Reset the backend when done:  curl -X POST $NOTES_ADMIN/admin/reset"
