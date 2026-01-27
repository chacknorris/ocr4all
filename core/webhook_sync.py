from __future__ import annotations
"""
Synchronous webhook utilities for Celery workers.
"""
import hashlib
import hmac
import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.auth import Webhook, WebhookDelivery, WEBHOOK_EVENTS


def sign_payload(payload: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for payload."""
    return hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()


def trigger_webhook_sync(
    event_type: str,
    payload: dict[str, Any],
    organization_id: Optional[UUID],
    db: Session,
) -> list[WebhookDelivery]:
    """
    Synchronous version of webhook trigger for Celery workers.

    Args:
        event_type: Type of event (e.g., "document.processed")
        payload: Event data
        organization_id: Organization to trigger for (if None, skip)
        db: Synchronous database session

    Returns:
        List of delivery records
    """
    if not organization_id:
        return []

    if event_type not in WEBHOOK_EVENTS:
        return []

    # Find active webhooks subscribed to this event
    webhooks = (
        db.query(Webhook)
        .filter(
            Webhook.organization_id == organization_id,
            Webhook.is_active == True,
        )
        .all()
    )

    # Filter webhooks subscribed to this event
    matching_webhooks = [w for w in webhooks if event_type in w.events]

    if not matching_webhooks:
        return []

    deliveries = []

    for webhook in matching_webhooks:
        delivery = deliver_webhook_sync(webhook, event_type, payload, db)
        deliveries.append(delivery)

    return deliveries


def deliver_webhook_sync(
    webhook: Webhook,
    event_type: str,
    payload: dict[str, Any],
    db: Session,
) -> WebhookDelivery:
    """
    Deliver a single webhook synchronously.
    """
    # Create delivery record
    delivery = WebhookDelivery(
        webhook_id=webhook.id,
        event_type=event_type,
        payload=payload,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)

    # Prepare request
    json_payload = json.dumps({
        "event": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "data": payload,
    }, default=str)

    signature = sign_payload(json_payload, webhook.secret)

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": f"sha256={signature}",
        "X-Webhook-Event": event_type,
        "X-Webhook-Delivery": str(delivery.id),
    }

    if webhook.headers:
        headers.update(webhook.headers)

    # Attempt delivery
    for attempt in range(1, webhook.retry_count + 1):
        start_time = datetime.utcnow()
        try:
            with httpx.Client(timeout=webhook.timeout_seconds) as client:
                response = client.post(
                    webhook.url,
                    content=json_payload,
                    headers=headers,
                )

            response_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            delivery.response_status = response.status_code
            delivery.response_body = response.text[:5000] if response.text else None
            delivery.response_time_ms = response_time
            delivery.attempt_count = attempt
            delivery.success = 200 <= response.status_code < 300
            db.commit()

            if delivery.success:
                break

        except Exception as e:
            response_time = int(
                (datetime.utcnow() - start_time).total_seconds() * 1000
            )

            delivery.error_message = str(e)[:1000]
            delivery.response_time_ms = response_time
            delivery.attempt_count = attempt
            delivery.success = False
            db.commit()

            if attempt < webhook.retry_count:
                import time
                time.sleep(2 ** attempt)  # Exponential backoff

    return delivery


def trigger_document_event(
    event_type: str,
    document_id: UUID,
    doc_type: str,
    organization_id: Optional[UUID],
    db: Session,
    extra_data: Optional[dict] = None,
):
    """
    Convenience function to trigger document-related webhook events.

    Args:
        event_type: One of document.uploaded, document.processed, etc.
        document_id: Document UUID
        doc_type: Document type string
        organization_id: Organization UUID (from API key)
        db: Database session
        extra_data: Additional data to include in payload
    """
    payload = {
        "document_id": str(document_id),
        "doc_type": doc_type,
        "timestamp": datetime.utcnow().isoformat(),
    }

    if extra_data:
        payload.update(extra_data)

    return trigger_webhook_sync(event_type, payload, organization_id, db)
