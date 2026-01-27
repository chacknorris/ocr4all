from __future__ import annotations
"""
Authentication and authorization service.
"""
from datetime import datetime, timedelta
from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from models.auth import ApiKey, ApiKeyUsage, Organization

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class AuthContext:
    """Authentication context for the current request."""

    def __init__(
        self,
        api_key: Optional[ApiKey] = None,
        organization: Optional[Organization] = None,
    ):
        self.api_key = api_key
        self.organization = organization
        self.is_authenticated = api_key is not None

    @property
    def org_id(self) -> Optional[UUID]:
        return self.organization.id if self.organization else None

    def has_scope(self, scope: str) -> bool:
        if not self.api_key:
            return False
        return scope in self.api_key.scopes or "admin" in self.api_key.scopes


async def get_api_key(
    api_key: Optional[str] = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Optional[ApiKey]:
    """Validate API key and return the key object."""
    if not api_key:
        return None

    # Hash the provided key
    key_hash = ApiKey.hash_key(api_key)

    # Find matching key
    query = (
        select(ApiKey)
        .where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active == True,
        )
    )
    result = await db.execute(query)
    db_key = result.scalar_one_or_none()

    if not db_key:
        return None

    # Check expiration
    if db_key.expires_at and db_key.expires_at < datetime.utcnow():
        return None

    # Update last used
    await db.execute(
        update(ApiKey)
        .where(ApiKey.id == db_key.id)
        .values(last_used_at=datetime.utcnow())
    )
    await db.commit()

    return db_key


async def get_auth_context(
    api_key: Optional[ApiKey] = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    """Get authentication context for the current request."""
    if not api_key:
        return AuthContext()

    # Load organization
    query = select(Organization).where(Organization.id == api_key.organization_id)
    result = await db.execute(query)
    organization = result.scalar_one_or_none()

    return AuthContext(api_key=api_key, organization=organization)


async def require_auth(
    auth: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    """Require authentication - raises 401 if not authenticated."""
    if not auth.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return auth


async def require_scope(scope: str):
    """Factory for scope-checking dependency."""
    async def check_scope(auth: AuthContext = Depends(require_auth)) -> AuthContext:
        if not auth.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{scope}' required",
            )
        return auth
    return check_scope


async def require_read(auth: AuthContext = Depends(require_auth)) -> AuthContext:
    """Require read scope."""
    if not auth.has_scope("read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read scope required",
        )
    return auth


async def require_write(auth: AuthContext = Depends(require_auth)) -> AuthContext:
    """Require write scope."""
    if not auth.has_scope("write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write scope required",
        )
    return auth


async def require_admin(auth: AuthContext = Depends(require_auth)) -> AuthContext:
    """Require admin scope."""
    if not auth.has_scope("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin scope required",
        )
    return auth


async def check_rate_limit(
    auth: AuthContext = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> AuthContext:
    """Check rate limit for API key."""
    if not auth.api_key:
        return auth

    # Count requests in last hour
    hour_ago = datetime.utcnow() - timedelta(hours=1)
    query = (
        select(ApiKeyUsage)
        .where(
            ApiKeyUsage.api_key_id == auth.api_key.id,
            ApiKeyUsage.created_at >= hour_ago,
        )
    )
    result = await db.execute(query)
    count = len(result.scalars().all())

    if count >= auth.api_key.rate_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Limit: {auth.api_key.rate_limit}/hour",
            headers={"Retry-After": "3600"},
        )

    return auth


async def log_api_usage(
    api_key_id: UUID,
    endpoint: str,
    method: str,
    status_code: int,
    response_time_ms: int,
    ip_address: Optional[str],
    user_agent: Optional[str],
    db: AsyncSession,
):
    """Log API usage for analytics and rate limiting."""
    usage = ApiKeyUsage(
        api_key_id=api_key_id,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        response_time_ms=response_time_ms,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(usage)
    await db.commit()


# Optional auth - allows unauthenticated access but provides context if authenticated
OptionalAuth = Annotated[AuthContext, Depends(get_auth_context)]

# Required auth variants
RequireAuth = Annotated[AuthContext, Depends(require_auth)]
RequireRead = Annotated[AuthContext, Depends(require_read)]
RequireWrite = Annotated[AuthContext, Depends(require_write)]
RequireAdmin = Annotated[AuthContext, Depends(require_admin)]
