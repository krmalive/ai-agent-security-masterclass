#!/bin/sh
# One-shot Vault configuration for the brokered-credentials lab.
# Runs inside a vault image container with VAULT_ADDR/VAULT_TOKEN set by compose.
# Everything an operator would do out-of-band lives here — the agent only ever
# gets the AppRole identity this script drops into /broker.
set -e

echo "[init] waiting for Vault to be ready at $VAULT_ADDR ..."
until vault status >/dev/null 2>&1; do
  sleep 1
done
echo "[init] Vault is up."

# ---------------------------------------------------------------------------
# 1. Audit device — every request/response is logged (secrets are HMAC'd).
#    The agent-app mounts this same volume read-only and renders it at /audit.
# ---------------------------------------------------------------------------
if ! vault audit list 2>/dev/null | grep -q '^file/'; then
  vault audit enable file file_path=/vault/logs/vault_audit.log
  echo "[init] file audit device enabled -> /vault/logs/vault_audit.log"
fi

# ---------------------------------------------------------------------------
# 2. Database secrets engine — dynamic, short-lived Postgres credentials.
#    Vault owns the real superuser credential; the agent only ever receives
#    freshly-minted SELECT-only users that expire after 3 minutes.
# ---------------------------------------------------------------------------
vault secrets enable database 2>/dev/null || true

vault write database/config/customersdb \
  plugin_name=postgresql-database-plugin \
  allowed_roles=agent-db-ro \
  connection_url="postgresql://{{username}}:{{password}}@postgres:5432/customers?sslmode=disable" \
  username="vaultadmin" \
  password="vaultadmin-password"

# SELECT-only: this is the least-privilege lesson. Ask the agent to DELETE a
# row and Postgres itself will refuse — the brokered role has no such grant.
vault write database/roles/agent-db-ro \
  db_name=customersdb \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  default_ttl=3m \
  max_ttl=15m
echo "[init] database secrets engine configured (role: agent-db-ro, TTL 3m)."

# ---------------------------------------------------------------------------
# 3. KV v2 — the static bearer token for the internal orders API.
#    (dev mode already mounts kv-v2 at secret/; enable is a no-op guard)
# ---------------------------------------------------------------------------
vault secrets enable -path=secret kv-v2 2>/dev/null || true
vault kv put secret/orders-api token="${ORDERS_API_TOKEN}"
echo "[init] orders API token stored at secret/orders-api."

# ---------------------------------------------------------------------------
# 4. Policy — the ONLY things the agent's identity may do in Vault.
# ---------------------------------------------------------------------------
vault policy write agent-policy - <<'EOF'
# Mint short-lived read-only Postgres credentials
path "database/creds/agent-db-ro" {
  capabilities = ["read"]
}

# Read the orders API bearer token
path "secret/data/orders-api" {
  capabilities = ["read"]
}
EOF
echo "[init] agent-policy written."

# ---------------------------------------------------------------------------
# 5. AppRole — the machine identity the agent logs in with.
#    role_id ~ "username" (not secret), secret_id ~ "password" (secret zero).
#    In production the secret_id is delivered via a trusted orchestrator or
#    response wrapping; here compose drops both into a shared volume.
# ---------------------------------------------------------------------------
vault auth enable approle 2>/dev/null || true

vault write auth/approle/role/agent-app \
  token_policies=agent-policy \
  token_ttl=30m \
  token_max_ttl=2h \
  secret_id_ttl=24h \
  secret_id_num_uses=0

vault read -field=role_id auth/approle/role/agent-app/role-id > /broker/role_id
vault write -f -field=secret_id auth/approle/role/agent-app/secret-id > /broker/secret_id
chmod 0644 /broker/role_id /broker/secret_id
echo "[init] AppRole 'agent-app' created; identity written to /broker."

echo "[init] Vault configuration complete."
