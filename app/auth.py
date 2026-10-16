import hmac
import os
from typing import Optional
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


bearer_scheme = HTTPBearer(auto_error=False)
TENANT_BY_TOKEN = {
    "demo-tenant": "tenant-123",
    "customer-support": "tenant-123",
}


def _token(credentials: Optional[HTTPAuthorizationCredentials]) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required.")

    token = credentials.credentials.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def authenticate_tenant(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> str:
    tenant_id = TENANT_BY_TOKEN.get(_token(credentials))
    if tenant_id is None:
        raise HTTPException(status_code=401, detail="Invalid or unknown tenant session.")

    telemetry = getattr(request.state, "telemetry", None)
    if telemetry is not None:
        telemetry["tenant_id"] = tenant_id
        telemetry["user_id"] = str(database_user_id(tenant_id))
    return tenant_id


def authenticate_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> None:
    token = _token(credentials)
    admin_token = os.getenv("API_ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=503, detail="Admin authentication is not configured.")
    if any(hmac.compare_digest(admin_token, tenant_token) for tenant_token in TENANT_BY_TOKEN):
        raise HTTPException(status_code=503, detail="Admin credential must be separate from tenant credentials.")
    if not hmac.compare_digest(token, admin_token):
        raise HTTPException(status_code=403, detail="Administrator access required.")


def database_tenant_id(tenant_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"customer-support-tenant:{tenant_id}")


def database_user_id(tenant_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"customer-support-service-user:{tenant_id}")


def database_conversation_id(conversation_id: str, tenant_id: str) -> UUID:
    try:
        return UUID(conversation_id)
    except ValueError:
        return uuid5(NAMESPACE_URL, f"customer-support-conversation:{tenant_id}:{conversation_id}")
