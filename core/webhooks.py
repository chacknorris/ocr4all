"""
Webhook delivery service for event notifications.
"""
import asyncio
import hashlib
import hmac
import json
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.auth import Webhook, WebhookDelivery, WEBHOOK_EVENTS


class WebhookService:
    """Service for delivering webhook events."""

    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries

    def sign_payload(self, payload: str, secret: str) -> str:
        """Generate HMAC-SHA256 signature for payload."""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

    async def deliver(
        self,
        webhook: Webhook,
        event_type: str,
        payload: dict[str, Any],
        db: AsyncSession,
    ) -> WebhookDelivery:
        """
        Deliver a webhook event.

        Args:
            webhook: Webhook configuration
            event_type: Type of event (e.g., "document.processed")
            payload: Event payload data
            db: Database session

        Returns:
            WebhookDelivery record
        """
        # Create delivery record
        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event_type=event_type,
            payload=payload,
        )
        db.add(delivery)
        await db.commit()
        await db.refresh(delivery)

        # Prepare request
        json_payload = json.dumps({
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload,
        }, default=str)

        signature = self.sign_payload(json_payload, webhook.secret)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": f"sha256={signature}",
            "X-Webhook-Event": event_type,
            "X-Webhook-Delivery": str(delivery.id),
        }

        # Add custom headers if configured
        if webhook.headers:
            headers.update(webhook.headers)

        # Attempt delivery with retries
        async with httpx.AsyncClient(timeout=webhook.timeout_seconds) as client:
            for attempt in range(1, webhook.retry_count + 1):
                start_time = datetime.utcnow()
                try:
                    response = await client.post(
                        webhook.url,
                        content=json_payload,
                        headers=headers,
                    )

                    response_time = int(
                        (datetime.utcnow() - start_time).total_seconds() * 1000
                    )

                    # Update delivery record
                    await db.execute(
                        update(WebhookDelivery)
                        .where(WebhookDelivery.id == delivery.id)
                        .values(
                            response_status=response.status_code,
                            response_body=response.text[:5000] if response.text else None,
                            response_time_ms=response_time,
                            attempt_count=attempt,
                            success=200 <= response.status_code < 300,
                        )
                    )
                    await db.commit()

                    if 200 <= response.status_code < 300:
                        break

                except Exception as e:
                    response_time = int(
                        (datetime.utcnow() - start_time).total_seconds() * 1000
                    )

                    await db.execute(
                        update(WebhookDelivery)
                        .where(WebhookDelivery.id == delivery.id)
                        .values(
                            error_message=str(e)[:1000],
                            response_time_ms=response_time,
                            attempt_count=attempt,
                            success=False,
                        )
                    )
                    await db.commit()

                    if attempt < webhook.retry_count:
                        # Exponential backoff
                        await asyncio.sleep(2 ** attempt)

        # Refresh and return delivery
        await db.refresh(delivery)
        return delivery


async def trigger_webhook_event(
    event_type: str,
    payload: dict[str, Any],
    organization_id: UUID,
    db: AsyncSession,
) -> list[WebhookDelivery]:
    """
    Trigger webhook event for all matching webhooks.

    Args:
        event_type: Type of event
        payload: Event data
        organization_id: Organization to trigger for
        db: Database session

    Returns:
        List of delivery records
    """
    if event_type not in WEBHOOK_EVENTS:
        raise ValueError(f"Unknown event type: {event_type}")

    # Find active webhooks subscribed to this event
    query = (
        select(Webhook)
        .where(
            Webhook.organization_id == organization_id,
            Webhook.is_active == True,
        )
    )
    result = await db.execute(query)
    webhooks = result.scalars().all()

    # Filter webhooks subscribed to this event
    matching_webhooks = [
        w for w in webhooks
        if event_type in w.events
    ]

    if not matching_webhooks:
        return []

    # Deliver to all matching webhooks
    service = WebhookService()
    deliveries = []

    for webhook in matching_webhooks:
        delivery = await service.deliver(webhook, event_type, payload, db)
        deliveries.append(delivery)

    return deliveries


async def get_webhook_deliveries(
    webhook_id: UUID,
    db: AsyncSession,
    limit: int = 50,
) -> list[WebhookDelivery]:
    """Get recent deliveries for a webhook."""
    query = (
        select(WebhookDelivery)
        .where(WebhookDelivery.webhook_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def retry_delivery(
    delivery_id: UUID,
    db: AsyncSession,
) -> WebhookDelivery | None:
    """Retry a failed webhook delivery."""
    # Get delivery
    query = (
        select(WebhookDelivery)
        .where(WebhookDelivery.id == delivery_id)
    )
    result = await db.execute(query)
    delivery = result.scalar_one_or_none()

    if not delivery:
        return None

    # Get webhook
    query = select(Webhook).where(Webhook.id == delivery.webhook_id)
    result = await db.execute(query)
    webhook = result.scalar_one_or_none()

    if not webhook or not webhook.is_active:
        return None

    # Re-deliver
    service = WebhookService()
    return await service.deliver(
        webhook,
        delivery.event_type,
        delivery.payload,
        db,
    )
