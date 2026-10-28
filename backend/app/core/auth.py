import hmac
from typing import Optional
from fastapi import Request, Header, Query, status
from app.core.config import settings
from app.core.errors import AppException, AppErrorCode

def get_current_identity(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    x_client_id: Optional[str] = Header(None, alias="X-Client-ID"),
    api_key_query: Optional[str] = Query(None, alias="api_key"),
) -> str:
    """
    Validates authentication credentials and determines caller session/owner identity.
    - If settings.REQUIRE_AUTH is True or settings.API_KEY is non-empty:
        Enforces a valid API key passed via X-API-Key, Authorization: Bearer, or query parameter.
    - Resolves caller owner_id from X-Session-ID or X-Client-ID.
    - In local-first dev mode (REQUIRE_AUTH=False, no API_KEY configured), requests are permitted seamlessly.
    """
    provided_key = None
    if x_api_key and x_api_key.strip():
        provided_key = x_api_key.strip()
    elif authorization and authorization.strip().lower().startswith("bearer "):
        provided_key = authorization.strip()[7:].strip()
    elif api_key_query and api_key_query.strip():
        provided_key = api_key_query.strip()

    # Determine whether authentication is required
    must_authenticate = settings.REQUIRE_AUTH or bool(settings.API_KEY)
    if must_authenticate:
        if not provided_key:
            raise AppException(
                code=AppErrorCode.UNAUTHORIZED,
                message="Authentication required: missing API key or Authorization header.",
                status_code=status.HTTP_401_UNAUTHORIZED
            )
        if not settings.API_KEY or not hmac.compare_digest(provided_key, settings.API_KEY):
            raise AppException(
                code=AppErrorCode.UNAUTHORIZED,
                message="Authentication failed: invalid API key.",
                status_code=status.HTTP_401_UNAUTHORIZED
            )

    # Determine caller ownership/session ID
    session_id = x_session_id or x_client_id
    if session_id and session_id.strip():
        return session_id.strip()
    return "default"
