"""
Reusable JWT authentication for AI agents (FastAPI)
"""
import os
from fastapi import Depends, HTTPException, Header
from typing import Dict, Any, Optional
import jwt

PUB_KEY_PATH = os.getenv("PUB_KEY_PATH")
if not PUB_KEY_PATH:
    raise RuntimeError("PUB_KEY_PATH environment variable not set")
with open(PUB_KEY_PATH, "r") as f:
    PUBLIC_KEY = f.read()

# Dependency for FastAPI endpoints
def get_current_user_claims(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]
    try:
        claims = jwt.decode(token, key=PUBLIC_KEY, algorithms=["RS256"])
        return claims
    except jwt.exceptions.InvalidTokenError as err:
        raise HTTPException(status_code=401, detail=f"Invalid token: {err}")
