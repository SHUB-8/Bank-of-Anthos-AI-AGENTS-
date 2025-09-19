# GENERATED: Orchestrator - produced by Gemini CLI. Do not include mock or dummy data in production code.

import os
import base64
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Dict
from middleware import get_logger

# This dependency will extract the token from the Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") 

# Load the public key from file
try:
    with open(os.getenv("JWT_PUBLIC_KEY_PATH"), "r") as f:
        PUBLIC_KEY = f.read()
except (IOError, TypeError):
    # Fallback for environments where the key is passed directly
    PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY")

ALGORITHM = os.getenv("ALGORITHM", "RS256")



async def get_current_user_claims(token: str = Depends(oauth2_scheme)) -> Dict[str, any]:
    """
    A FastAPI dependency that validates the JWT locally using the public key
    and returns the decoded token claims.
    
    This is the single source of truth for user identity.
    """
    try:
        # PyJWT will verify the signature and expiration date
        payload = jwt.decode(
            token, 
            JWT_PUBLIC_KEY, 
            algorithms=["RS256"], 
            options={"verify_aud": False} # Audience verification can be added if needed
        )
        
        account_id: str = payload.get("acct")
        username: str = payload.get("user")

        if account_id is None or username is None:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid token: missing required claims (acct, user)",
            )
        
        # Return a dictionary with the essential claims
        return {"account_id": account_id, "username": username}

    except jwt.ExpiredSignatureError:
        logger = get_logger()
        logger.warning("JWT validation failed: Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        logger = get_logger()
        logger.error(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )