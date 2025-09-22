# auth.py
"""
Enhanced JWT Authentication Module for FastAPI

This module provides JWT-based authentication with proper token extraction
for downstream service calls in the Bank of Anthos platform.
"""
import os
import logging
from typing import Dict, Any, Optional, List
import jwt
from fastapi import Depends, HTTPException, Header

logger = logging.getLogger(__name__)

# The RS256 public key is loaded from environment variable
PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY")
if not PUBLIC_KEY:
    raise RuntimeError("FATAL: JWT_PUBLIC_KEY environment variable is not set.")

def get_current_user_claims(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    FastAPI dependency to validate a JWT and extract its claims.
    
    Returns:
        Dictionary containing JWT claims plus the raw token for downstream services
        
    Raises:
        HTTPException: If authentication fails
    """
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("Missing or invalid Authorization header")
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid 'Authorization: Bearer <token>' header."
        )

    # Extract the token
    try:
        token = authorization.split(" ", 1)[1]
    except IndexError:
        logger.warning("Malformed Authorization header")
        raise HTTPException(
            status_code=401,
            detail="Malformed Authorization header."
        )

    try:
        # Decode and validate the JWT
        claims = jwt.decode(
            token, 
            key=PUBLIC_KEY, 
            algorithms=["RS256"],
            options={"verify_exp": True, "verify_aud": False}  # Verify expiration but not audience
        )
        
        # Add the raw token to claims for downstream service calls
        claims["_raw_token"] = token
        
        # Log successful authentication (without sensitive data)
        account_id = claims.get("accountId", "unknown")
        logger.debug(f"Successfully authenticated user with account_id: {account_id}")
        
        return claims
        
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise HTTPException(
            status_code=401, 
            detail="Token has expired. Please log in again."
        )
    except jwt.InvalidTokenError as err:
        logger.warning(f"Invalid JWT token: {str(err)}")
        raise HTTPException(
            status_code=401, 
            detail=f"Invalid authentication token: {str(err)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during JWT validation: {str(e)}")
        raise HTTPException(
            status_code=401, 
            detail="Authentication failed."
        )

def extract_account_id(claims: Dict[str, Any]) -> str:
    """
    Extract account ID from JWT claims with validation.
    
    Args:
        claims: JWT claims dictionary
        
    Returns:
        Account ID string
        
    Raises:
        HTTPException: If account ID is missing or invalid
    """
    account_id = claims.get("accountId")
    
    if not account_id:
        logger.error("JWT token is missing required 'accountId' claim")
        raise HTTPException(
            status_code=401,
            detail="Authentication token is missing required account information."
        )
    
    if not isinstance(account_id, str) or not account_id.strip():
        logger.error(f"Invalid account ID in JWT claims: {account_id}")
        raise HTTPException(
            status_code=401,
            detail="Authentication token contains invalid account information."
        )
    
    return account_id.strip()

def get_auth_header_for_downstream(claims: Dict[str, Any]) -> str:
    """
    Get properly formatted Authorization header for downstream service calls.
    
    Args:
        claims: JWT claims dictionary (must contain _raw_token)
        
    Returns:
        Authorization header string
        
    Raises:
        HTTPException: If raw token is not available
    """
    raw_token = claims.get("_raw_token")
    
    if not raw_token:
        logger.error("Raw JWT token not available in claims")
        raise HTTPException(
            status_code=500,
            detail="Authentication context is invalid."
        )
    
    return f"Bearer {raw_token}"

def validate_jwt_structure(token: str) -> bool:
    """
    Validate basic JWT structure without verifying signature.
    Useful for quick validation before expensive verification.
    
    Args:
        token: JWT token string
        
    Returns:
        True if structure is valid, False otherwise
    """
    try:
        parts = token.split('.')
        return len(parts) == 3  # header.payload.signature
    except Exception:
        return False

class AuthContext:
    """
    Context class for managing authentication information throughout a request.
    """
    
    def __init__(self, claims: Dict[str, Any]):
        self.claims = claims
        self._account_id = None
        self._auth_header = None
    
    @property
    def account_id(self) -> str:
        """Get account ID with caching"""
        if self._account_id is None:
            self._account_id = extract_account_id(self.claims)
        return self._account_id
    
    @property
    def auth_header(self) -> str:
        """Get auth header for downstream services with caching"""
        if self._auth_header is None:
            self._auth_header = get_auth_header_for_downstream(self.claims)
        return self._auth_header
    
    @property
    def username(self) -> Optional[str]:
        """Get username from claims if available"""
        return self.claims.get("username") or self.claims.get("sub")
    
    @property
    def email(self) -> Optional[str]:
        """Get email from claims if available"""
        return self.claims.get("email")
    
    @property
    def roles(self) -> List[str]:
        """Get user roles from claims"""
        roles = self.claims.get("roles", [])
        if isinstance(roles, str):
            return [roles]
        elif isinstance(roles, list):
            return roles
        else:
            return []
    
    def has_role(self, role: str) -> bool:
        """Check if user has a specific role"""
        return role in self.roles
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging (without sensitive data)"""
        return {
            "account_id": self.account_id,
            "username": self.username,
            "email": self.email,
            "roles": self.roles,
            "has_token": bool(self.claims.get("_raw_token"))
        }

def get_auth_context(claims: Dict[str, Any] = Depends(get_current_user_claims)) -> AuthContext:
    """
    FastAPI dependency to get AuthContext object.
    
    Returns:
        AuthContext object with convenient access to auth information
    """
    return AuthContext(claims)