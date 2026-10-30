"""The credential broker: the ONLY module in the agent that talks to Vault.

The security model this lab teaches:

  * The agent's code and config contain ZERO long-lived secrets. Its only
    identity is an AppRole (role_id + secret_id) delivered out-of-band by the
    operator (here: the vault-init container via a shared volume).
  * Postgres credentials are DYNAMIC: minted by Vault's database secrets
    engine per lease, SELECT-only, and dead 3 minutes later. Stealing one
    buys an attacker a read-only user with a countdown timer.
  * The orders API token is STATIC but brokered: it lives in Vault KV and is
    fetched at call time, so rotating it in Vault rotates it for the agent —
    no redeploy, no .env edits.
  * Every fetch is captured by Vault's audit device — see the /audit page.
"""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

import hvac
import psycopg

VAULT_ADDR = os.getenv("VAULT_ADDR", "http://vault:8200")
BROKER_CREDS_DIR = os.getenv("BROKER_CREDS_DIR", "/broker")
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_NAME = os.getenv("DB_NAME", "customers")

# Renew this many seconds before expiry so a tool call never lands on a
# credential that dies mid-query.
LEASE_SLACK_SECONDS = 15
API_TOKEN_CACHE_SECONDS = 60


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")


class VaultBroker:
    """AppRole login + credential caching, with an event log for the UI."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._client: hvac.Client | None = None
        self._token_expires_at: float = 0.0
        self._token_ttl: int = 0
        self._token_accessor: str = ""
        self._token_policies: list[str] = []

        self._db_creds: dict | None = None  # username/password/lease_id/ttl/acquired_at
        self._api_token: str | None = None
        self._api_token_fetched_at: float = 0.0

        self.events: list[dict] = []

    # ----- internals -------------------------------------------------------

    def _log(self, kind: str, detail: str) -> None:
        self.events.insert(0, {"time": _now(), "kind": kind, "detail": detail})
        del self.events[100:]

    def _read_identity(self) -> tuple[str, str]:
        try:
            with open(os.path.join(BROKER_CREDS_DIR, "role_id")) as f:
                role_id = f.read().strip()
            with open(os.path.join(BROKER_CREDS_DIR, "secret_id")) as f:
                secret_id = f.read().strip()
        except FileNotFoundError as exc:
            raise RuntimeError(
                "AppRole identity not found in /broker — has the vault-init "
                "container completed? (docker compose logs vault-init)"
            ) from exc
        return role_id, secret_id

    def _vault(self) -> hvac.Client:
        """Return an authenticated client, logging in via AppRole when the
        cached token is missing or about to expire."""
        if self._client is not None and time.monotonic() < self._token_expires_at - LEASE_SLACK_SECONDS:
            return self._client

        role_id, secret_id = self._read_identity()
        client = hvac.Client(url=VAULT_ADDR)
        resp = client.auth.approle.login(role_id=role_id, secret_id=secret_id)
        auth = resp["auth"]
        self._client = client
        self._token_ttl = auth["lease_duration"]
        self._token_expires_at = time.monotonic() + auth["lease_duration"]
        self._token_accessor = auth["accessor"]
        self._token_policies = auth["token_policies"]
        self._log(
            "approle-login",
            f"Logged into Vault via AppRole; token policies={self._token_policies}, "
            f"TTL {self._token_ttl}s. The agent holds a scoped Vault token — not the secrets themselves.",
        )
        return client

    # ----- Postgres: dynamic credentials -----------------------------------

    def db_seconds_remaining(self) -> int:
        if self._db_creds is None:
            return 0
        return max(0, int(self._db_creds["expires_at"] - time.monotonic()))

    def get_db_credentials(self, force_new: bool = False) -> dict:
        with self._lock:
            if force_new:
                self._db_creds = None
                self._log("db-creds-discard", "Cached DB credentials discarded — next query mints a fresh user.")
            if self._db_creds is not None and self.db_seconds_remaining() > LEASE_SLACK_SECONDS:
                return self._db_creds

            if self._db_creds is not None:
                self._log(
                    "db-creds-expired",
                    f"Lease for {self._db_creds['username']} expired — Vault has already dropped that "
                    "Postgres role. Minting a replacement.",
                )

            resp = self._vault().read("database/creds/agent-db-ro")
            ttl = resp["lease_duration"]
            self._db_creds = {
                "username": resp["data"]["username"],
                "password": resp["data"]["password"],
                "lease_id": resp["lease_id"],
                "ttl": ttl,
                "acquired": _now(),
                "expires_at": time.monotonic() + ttl,
            }
            self._log(
                "db-creds-issued",
                f"Vault minted dynamic Postgres user {self._db_creds['username']} "
                f"(SELECT-only, lease {ttl}s). It will be dropped automatically at expiry.",
            )
            return self._db_creds

    def db_connection(self) -> psycopg.Connection:
        creds = self.get_db_credentials()
        return psycopg.connect(
            host=DB_HOST,
            dbname=DB_NAME,
            user=creds["username"],
            password=creds["password"],
            connect_timeout=5,
        )

    # ----- Orders API: brokered static token from KV ------------------------

    def get_api_token(self) -> str:
        with self._lock:
            if self._api_token is not None and time.monotonic() - self._api_token_fetched_at < API_TOKEN_CACHE_SECONDS:
                return self._api_token
            resp = self._vault().secrets.kv.v2.read_secret_version(
                path="orders-api", raise_on_deleted_version=True
            )
            self._api_token = resp["data"]["data"]["token"]
            self._api_token_fetched_at = time.monotonic()
            self._log(
                "kv-token-read",
                "Fetched orders API bearer token from Vault KV (secret/orders-api). "
                "Rotate it in Vault and the agent picks up the new value — no redeploy.",
            )
            return self._api_token

    # ----- status for the UI ------------------------------------------------

    def status(self) -> dict:
        db = None
        if self._db_creds is not None:
            db = {
                "username": self._db_creds["username"],
                "lease_id": self._db_creds["lease_id"],
                "ttl": self._db_creds["ttl"],
                "acquired": self._db_creds["acquired"],
                "seconds_remaining": self.db_seconds_remaining(),
            }
        token = None
        if self._client is not None:
            token = {
                "accessor": self._token_accessor,
                "policies": self._token_policies,
                "ttl": self._token_ttl,
            }
        api = None
        if self._api_token is not None:
            api = {"masked": self._api_token[:12] + "…", "source": "Vault KV secret/orders-api"}
        return {"vault_addr": VAULT_ADDR, "token": token, "db": db, "api": api}


broker = VaultBroker()
