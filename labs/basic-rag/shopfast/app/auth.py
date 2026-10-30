import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings
from .store import store

security = HTTPBearer()


def hash_password(password: str) -> str:
    return hashlib.sha256(f"shopfast:{password}".encode()).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return secrets.compare_digest(hash_password(password), password_hash)


def issue_tokens(user_id: int, role: str) -> dict:
    now = datetime.now(timezone.utc)
    access_claims = {
        "sub": str(user_id),
        "role": role,
        "iss": settings.jwt_issuer,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    refresh_token = secrets.token_urlsafe(40)
    store.refresh_tokens[refresh_token] = user_id
    return {
        "access_token": jwt.encode(access_claims, settings.jwt_secret, algorithm="HS256"),
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_minutes * 60,
    }


def current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
        )
        user = store.users.get(int(claims["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc
    if not user or not user["active"]:
        raise HTTPException(status_code=401, detail="Account unavailable")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user
