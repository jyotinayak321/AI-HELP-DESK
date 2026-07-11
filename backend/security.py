"""
security.py — JWT Authentication Dependency for FastAPI
=========================================================
This module validates Keycloak-issued JWT tokens on every protected request.

HOW IT WORKS:
  1. FastAPI calls `get_current_user` as a Depends() on each route.
  2. It extracts the Bearer token from the Authorization header.
  3. It fetches Keycloak's public key (JWKS) to verify the token's signature.
  4. It decodes the JWT and extracts the `preferred_username` (the Service No).
  5. It queries the PostgreSQL `user_roles` table to get the user's role.
  6. It returns a `CurrentUser` object containing service_no, role, and managed_application_id.

SAFETY TOGGLE:
  If settings.AUTH_ENABLED is False (the default in .env), this middleware
  returns a mock "dev user" on every request so the app works without Keycloak.
  Set AUTH_ENABLED=True in .env (or environment) to enforce real JWT validation.
"""

import httpx
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
# pyrefly: ignore [missing-import]
from sqlmodel import Session
from pydantic import BaseModel

from config import settings
from database import get_session
from models import UserRole

# ─────────────────────────────────────────────────────────────────────────────
# Data model returned by the auth dependency
# ─────────────────────────────────────────────────────────────────────────────

class CurrentUser(BaseModel):
    service_no: str
    role: str  # "operator" or "admin"
    managed_team: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Dev / mock user — used when AUTH_ENABLED=False
# ─────────────────────────────────────────────────────────────────────────────

DEV_USER = CurrentUser(
    service_no="DEV-00000",
    role="operator",
    managed_team=None,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fetch Keycloak's public key from the JWKS endpoint (cached)
# ─────────────────────────────────────────────────────────────────────────────

# Store the JWKS in a module-level variable so failures don't get cached.
_jwks_cache: dict | None = None

def _get_keycloak_public_key() -> dict:
    """
    Fetches the JWKS (public keys) from Keycloak's well-known endpoint.
    Cached in a module variable — but only on SUCCESS so failed fetches
    can be retried on the next request (e.g. while Keycloak is booting).
    """
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache

    jwks_url = (
        f"{settings.KEYCLOAK_URL}/realms/{settings.KEYCLOAK_REALM}"
        f"/protocol/openid-connect/certs"
    )
    print("\n========== KEYCLOAK CONFIG ==========")
    print("KEYCLOAK_URL:", settings.KEYCLOAK_URL)
    print("REALM:", settings.KEYCLOAK_REALM)
    print("JWKS URL:", jwks_url)
    print("====================================")
    try:
        response = httpx.get(jwks_url, timeout=5.0)
        print("JWKS HTTP Status:", response.status_code)
        print("JWKS Response:", response.text[:300])
        response.raise_for_status()
        _jwks_cache = response.json()
        return _jwks_cache
    except Exception:
        import traceback

        print("\n========== KEYCLOAK ERROR ==========")
        traceback.print_exc()
        print("===================================\n")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cannot reach Keycloak to fetch public key."
        )


# ─────────────────────────────────────────────────────────────────────────────
# HTTP Bearer scheme (reads "Authorization: Bearer <token>" from request)
# ─────────────────────────────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


# ─────────────────────────────────────────────────────────────────────────────
# Main auth dependency — call this with Depends() on protected routes
# ─────────────────────────────────────────────────────────────────────────────

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    session: Session = Depends(get_session),
) -> CurrentUser:
    """
    FastAPI dependency that validates the JWT and returns the current user.

    Usage:
        @router.get("/protected")
        def protected(user: CurrentUser = Depends(get_current_user)):
            return {"hello": user.service_no}
    """
    # ── DEV MODE: Skip all token checks ──────────────────────────────────────
    if not settings.AUTH_ENABLED:
        return DEV_USER

    # ── PRODUCTION: Require a valid Bearer token ──────────────────────────────
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in via Keycloak.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # ── Decode and validate the JWT ───────────────────────────────────────────
    try:
        jwks = _get_keycloak_public_key()
        # jose will pick the right key from the JWKS automatically.
        # Keycloak tokens for public clients often have no explicit audience,
        # or use 'account' — so we pass options to be lenient.
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        print("Starting JWT verification...")

        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )

        print("JWT verified successfully!")
    except HTTPException:
        raise  # Re-raise 503 from Keycloak being down
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Extract service number from token payload ─────────────────────────────
    service_no: Optional[str] = payload.get("preferred_username")
    if not service_no:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing 'preferred_username' claim.",
        )
    service_no = service_no.upper()

    # ── Look up user role in PostgreSQL ───────────────────────────────────────
    user_role = session.get(UserRole, service_no)
    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User '{service_no}' is not registered in the application. "
                   "Contact your administrator.",
        )

    return CurrentUser(
        service_no=user_role.service_no,
        role=user_role.role,
        managed_team=user_role.managed_team,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Role-specific guard dependencies (use these for persona-based access)
# ─────────────────────────────────────────────────────────────────────────────

def require_operator(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Only allows users with role='operator'."""
    if settings.AUTH_ENABLED and user.role != "operator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This action requires the Operator role.",
        )
    return user


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Only allows users with role='admin'."""
    if settings.AUTH_ENABLED and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This action requires the Admin role.",
        )
    return user
