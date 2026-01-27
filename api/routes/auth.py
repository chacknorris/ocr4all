from __future__ import annotations
"""
Authentication and organization management API routes.
"""
from datetime import datetime
from typing import Annotated, Optional, List, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import RequireAdmin, RequireAuth, AuthContext
from core.webhooks import get_webhook_deliveries, retry_delivery
from models import get_db
from models.auth import (
    ApiKey,
    ApiKeyScope,
    ApiKeyUsage,
    Organization,
    Webhook,
    WebhookDelivery,
    WEBHOOK_EVENTS,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# === Schemas ===

class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9-]+$")


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: List[str] = Field(default=["read"])
    expires_at: Optional[datetime] = None
    rate_limit: int = Field(default=1000, ge=1, le=100000)


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    scopes: List[str]
    is_active: bool
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    rate_limit: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreated(ApiKeyResponse):
    """Response when creating a new API key - includes the full key (only shown once)."""
    api_key: str


class WebhookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1)
    events: List[str] = Field(default=["document.processed"])
    retry_count: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=30, ge=5, le=120)
    headers: Optional[Dict[str, str]] = None


class WebhookResponse(BaseModel):
    id: UUID
    name: str
    url: str
    events: List[str]
    is_active: bool
    retry_count: int
    timeout_seconds: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryResponse(BaseModel):
    id: UUID
    event_type: str
    response_status: Optional[int] = None
    response_time_ms: Optional[int] = None
    attempt_count: int
    success: bool
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyUsageStats(BaseModel):
    total_requests: int
    requests_last_hour: int
    requests_last_24h: int
    avg_response_time_ms: Optional[float] = None
    error_rate: float


# === Organization Routes ===

@router.post("/organizations", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new organization (public endpoint for onboarding)."""
    # Check slug uniqueness
    existing = await db.execute(
        select(Organization).where(Organization.slug == data.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization slug already exists",
        )

    org = Organization(
        name=data.name,
        slug=data.slug,
    )
    db.add(org)
    await db.commit()
    await db.refresh(org)

    return org


@router.get("/organizations/me", response_model=OrganizationResponse)
async def get_current_organization(
    auth: RequireAuth,
):
    """Get current organization based on API key."""
    if not auth.organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return auth.organization


# === API Key Routes ===

@router.post("/api-keys", response_model=ApiKeyCreated, status_code=201)
async def create_api_key(
    data: ApiKeyCreate,
    auth: RequireAdmin,
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key for the organization."""
    # Validate scopes
    valid_scopes = {s.value for s in ApiKeyScope}
    for scope in data.scopes:
        if scope not in valid_scopes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid scope: {scope}. Valid scopes: {valid_scopes}",
            )

    # Generate key
    full_key, key_hash, key_prefix = ApiKey.generate_key()

    api_key = ApiKey(
        organization_id=auth.org_id,
        name=data.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=data.scopes,
        expires_at=data.expires_at,
        rate_limit=data.rate_limit,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    # Return response with full key (only shown once)
    return ApiKeyCreated(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        is_active=api_key.is_active,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        rate_limit=api_key.rate_limit,
        created_at=api_key.created_at,
        api_key=full_key,
    )


@router.get("/api-keys", response_model=List[ApiKeyResponse])
async def list_api_keys(
    auth: RequireAdmin,
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for the organization."""
    query = (
        select(ApiKey)
        .where(ApiKey.organization_id == auth.org_id)
        .order_by(ApiKey.created_at.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: UUID,
    auth: RequireAdmin,
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key."""
    query = select(ApiKey).where(
        ApiKey.id == key_id,
        ApiKey.organization_id == auth.org_id,
    )
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    api_key.is_active = False
    await db.commit()


@router.get("/api-keys/{key_id}/usage", response_model=ApiKeyUsageStats)
async def get_api_key_usage(
    key_id: UUID,
    auth: RequireAdmin,
    db: AsyncSession = Depends(get_db),
):
    """Get usage statistics for an API key."""
    # Verify key belongs to org
    query = select(ApiKey).where(
        ApiKey.id == key_id,
        ApiKey.organization_id == auth.org_id,
    )
    result = await db.execute(query)
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    from datetime import timedelta
    now = datetime.utcnow()
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(hours=24)

    # Total requests
    total_query = select(func.count()).where(ApiKeyUsage.api_key_id == key_id)
    total_result = await db.execute(total_query)
    total_requests = total_result.scalar() or 0

    # Requests last hour
    hour_query = select(func.count()).where(
        ApiKeyUsage.api_key_id == key_id,
        ApiKeyUsage.created_at >= hour_ago,
    )
    hour_result = await db.execute(hour_query)
    requests_last_hour = hour_result.scalar() or 0

    # Requests last 24h
    day_query = select(func.count()).where(
        ApiKeyUsage.api_key_id == key_id,
        ApiKeyUsage.created_at >= day_ago,
    )
    day_result = await db.execute(day_query)
    requests_last_24h = day_result.scalar() or 0

    # Average response time
    avg_query = select(func.avg(ApiKeyUsage.response_time_ms)).where(
        ApiKeyUsage.api_key_id == key_id,
        ApiKeyUsage.response_time_ms.isnot(None),
    )
    avg_result = await db.execute(avg_query)
    avg_response_time = avg_result.scalar()

    # Error rate (5xx responses)
    error_query = select(func.count()).where(
        ApiKeyUsage.api_key_id == key_id,
        ApiKeyUsage.status_code >= 500,
    )
    error_result = await db.execute(error_query)
    error_count = error_result.scalar() or 0
    error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0

    return ApiKeyUsageStats(
        total_requests=total_requests,
        requests_last_hour=requests_last_hour,
        requests_last_24h=requests_last_24h,
        avg_response_time_ms=float(avg_response_time) if avg_response_time else None,
        error_rate=error_rate,
    )


# === Webhook Routes ===

@router.get("/webhook-events")
async def list_webhook_events():
    """List available webhook event types."""
    return {"events": WEBHOOK_EVENTS}


@router.post("/webhooks", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    data: WebhookCreate,
    auth: RequireAdmin,
    db: AsyncSession = Depends(get_db),
):
    """Create a new webhook."""
    # Validate events
    for event in data.events:
        if event not in WEBHOOK_EVENTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid event: {event}. Valid events: {WEBHOOK_EVENTS}",
            )

    webhook = Webhook(
        organization_id=auth.org_id,
        name=data.name,
        url=data.url,
        secret=Webhook.generate_secret(),
        events=data.events,
        retry_count=data.retry_count,
        timeout_seconds=data.timeout_seconds,
        headers=data.headers,
    )
    db.add(webhook)
    await db.commit()
    await db.refresh(webhook)

    return webhook


@router.get("/webhooks", response_model=List[WebhookResponse])
async def list_webhooks(
    auth: RequireAdmin,
    db: AsyncSession = Depends(get_db),
):
    """List all webhooks for the organization."""
    query = (
        select(Webhook)
        .where(Webhook.organization_id == auth.org_id)
        .order_by(Webhook.created_at.desc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/webhooks/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: UUID,
    auth: RequireAdmin,
    db: AsyncSession = Depends(get_db),
):
    """Get webhook details."""
    query = select(Webhook).where(
        Webhook.id == webhook_id,
        Webhook.organization_id == auth.org_id,
    )
    result = await db.execute(query)
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    return webhook


@router.get("/webhooks/{webhook_id}/secret")
async def get_webhook_secret(
    webhook_id: UUID,
    auth: RequireAdmin,
    db: AsyncSession = Depends(get_db),
):
    """Get webhook signing secret."""
    query = select(Webhook).where(
        Webhook.id == webhook_id,
        Webhook.organization_id == auth.org_id,
    )
    result = await db.execute(query)
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    return {"secret": webhook.secret}


@router.patch("/webhooks/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: UUID,
    data: WebhookCreate,
    auth: RequireAdmin,
    db: AsyncSession = Depends(get_db),
):
    """Update webhook configuration."""
    query = select(Webhook).where(
        Webhook.id == webhook_id,
        Webhook.organization_id == auth.org_id,
    )
    result = await db.execute(query)
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    # Validate events
    for event in data.events:
        if event not in WEBHOOK_EVENTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid event: {event}",
            )

    webhook.name = data.name
    webhook.url = data.url
    webhook.events = data.events
    webhook.retry_count = data.retry_count
    webhook.timeout_seconds = data.timeout_seconds
    webhook.headers = data.headers

    await db.commit()
    await db.refresh(webhook)

    return webhook


@router.delete("/webhooks/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: UUID,
    auth: RequireAdmin,
    db: AsyncSession = Depends(get_db),
):
    """Delete a webhook."""
    query = select(Webhook).where(
        Webhook.id == webhook_id,
        Webhook.organization_id == auth.org_id,
    )
    result = await db.execute(query)
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    await db.delete(webhook)
    await db.commit()


@router.post("/webhooks/{webhook_id}/toggle", response_model=WebhookResponse)
async def toggle_webhook(
    webhook_id: UUID,
    auth: RequireAdmin,
    db: AsyncSession = Depends(get_db),
):
    """Toggle webhook active status."""
    query = select(Webhook).where(
        Webhook.id == webhook_id,
        Webhook.organization_id == auth.org_id,
    )
    result = await db.execute(query)
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    webhook.is_active = not webhook.is_active
    await db.commit()
    await db.refresh(webhook)

    return webhook


@router.get(
    "/webhooks/{webhook_id}/deliveries",
    response_model=List[WebhookDeliveryResponse],
)
async def list_webhook_deliveries(
    webhook_id: UUID,
    auth: RequireAdmin,
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List recent deliveries for a webhook."""
    # Verify webhook belongs to org
    query = select(Webhook).where(
        Webhook.id == webhook_id,
        Webhook.organization_id == auth.org_id,
    )
    result = await db.execute(query)
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    deliveries = await get_webhook_deliveries(webhook_id, db, limit)
    return deliveries


@router.post(
    "/webhooks/deliveries/{delivery_id}/retry",
    response_model=WebhookDeliveryResponse,
)
async def retry_webhook_delivery(
    delivery_id: UUID,
    auth: RequireAdmin,
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed webhook delivery."""
    # Get delivery and verify org ownership
    query = (
        select(WebhookDelivery)
        .join(Webhook)
        .where(
            WebhookDelivery.id == delivery_id,
            Webhook.organization_id == auth.org_id,
        )
    )
    result = await db.execute(query)
    delivery = result.scalar_one_or_none()

    if not delivery:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delivery not found",
        )

    new_delivery = await retry_delivery(delivery_id, db)

    if not new_delivery:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not retry delivery - webhook may be inactive",
        )

    return new_delivery
