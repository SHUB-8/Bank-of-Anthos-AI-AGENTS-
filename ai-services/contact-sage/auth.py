# auth.py
"""
Reusable JWT Authentication Module for FastAPI

This module provides a dependency for FastAPI endpoints to enforce JWT-based
authentication. It decodes and validates a Bearer token using a public key.
"""
import os
from typing import Dict, Any, Optional
import jwt
from fastapi import Depends, HTTPException, Header

# The RS256 public key is loaded directly from an environment variable.
PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY")
if not PUBLIC_KEY:
    raise RuntimeError("FATAL: JWT_PUBLIC_KEY environment variable not set.")

def get_current_user_claims(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    FastAPI dependency to validate a JWT and extract its claims.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid 'Authorization: Bearer <token>' header."
        )

    token = authorization.split(" ", 1)[1]

    try:
        claims = jwt.decode(token, key=PUBLIC_KEY, algorithms=["RS256"])
        return claims
    except jwt.exceptions.InvalidTokenError as err:
        raise HTTPException(status_code=401, detail=f"Invalid token: {err}")