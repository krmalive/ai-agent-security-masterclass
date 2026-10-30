"""
auth-server : the custom token-verification endpoint you develop.

This is the piece the lab brief asks for: "token based authentication that is
verified by an endpoint that you develop". No Azure AD, no third party.

It exposes an OAuth 2.0 Token-Introspection style endpoint (modelled on
RFC 7662). The gateway calls POST /introspect with a token and gets back
whether the token is active, who the subject is, and which tools they may use.

Tokens live in users.json. In the real world these would be signed JWTs in a
database; opaque tokens in a JSON file keep the lab readable.
"""
import json
import os

from fastapi import FastAPI, Form
from fastapi.responses import JSONResponse

app = FastAPI(title="auth-server")

USERS_FILE = os.environ.get("USERS_FILE", "users.json")


def _load_users():
    with open(USERS_FILE) as f:
        return json.load(f)


@app.get("/health")
def health():
    return {"status": "ok", "server": "auth-server"}


@app.post("/introspect")
def introspect(token: str = Form(...)):
    """
    RFC 7662-style introspection.

    Request:  application/x-www-form-urlencoded  ->  token=<opaque token>
    Response: {"active": bool, "sub": str, "scope": str, "allowed_tools": [...]}

    An unknown or revoked token returns {"active": false} and nothing else,
    exactly as the RFC prescribes -- never leak details about invalid tokens.
    """
    users = _load_users()
    record = users.get(token)

    if not record or not record.get("active", False):
        return JSONResponse({"active": False})

    return JSONResponse(
        {
            "active": True,
            "sub": record["sub"],
            "scope": " ".join(record.get("roles", [])),
            "roles": record.get("roles", []),
            "allowed_tools": record.get("allowed_tools", []),
        }
    )
