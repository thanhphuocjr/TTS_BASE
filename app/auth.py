"""Bearer-token authentication dependency."""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import API_KEY

_security = HTTPBearer()


def require_api_key(creds: HTTPAuthorizationCredentials = Depends(_security)) -> None:
    if creds.credentials != API_KEY:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "invalid_api_key", "message": "Invalid API key"}},
        )
