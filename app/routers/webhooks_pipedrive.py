"""
Pipedrive webhooks router.

Receives and processes webhook events from Pipedrive.
"""
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_pipedrive_client, get_audit_service
from app.services.pipedrive import PipedriveClient
from app.services.audit import AuditService
from app.repositories.customers_repo import CustomersRepository
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/webhooks",
    tags=["webhooks"],
)


@router.get(
    "/pipedrive/verify",
    summary="Verify webhook endpoint",
    description="Endpoint for Pipedrive webhook verification",
)
async def verify_webhook():
    """
    Verify webhook endpoint.
    
    - Returns success for Pipedrive verification
    - No authentication required (public endpoint)
    """
    return {"status": "ok", "message": "Webhook endpoint is active"}


@router.post(
    "/pipedrive",
    summary="Receive Pipedrive webhook",
    description="Process incoming webhook events from Pipedrive",
)
async def receive_pipedrive_webhook(
    request: Request,
    x_pipedrive_signature: str | None = Header(None, alias="X-Pipedrive-Signature"),
    db: AsyncSession = Depends(get_db),
    pipedrive: PipedriveClient = Depends(get_pipedrive_client),
    audit: AuditService = Depends(get_audit_service),
):
    """
    Receive and process Pipedrive webhook events.
    
    - Validates webhook signature
    - Processes organization, person, and deal events
    - Syncs data with local database
    - Logs all events
    """
    try:
        # Get raw body
        body = await request.body()
        body_str = body.decode("utf-8")
        
        # Validate signature
        if x_pipedrive_signature:
            is_valid = await pipedrive.validate_webhook_signature(
                payload=body_str,
                signature=x_pipedrive_signature,
            )
            if not is_valid:
                logger.warning(
                    "invalid_webhook_signature",
                    signature=x_pipedrive_signature,
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid webhook signature",
                )
        
        # Parse JSON
        import json
        payload = json.loads(body_str)
        
        # Parse webhook event
        event = await pipedrive.parse_webhook_event(payload)
        
        logger.info(
            "webhook_received",
            event_type=event.event_type.value,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
        )
        
        # Process event based on type
        await process_webhook_event(event, db, audit)
        
        # Audit log
        await audit.log(
            action="webhook_received",
            entity_type="webhook",
            entity_id=str(event.entity_id),
            actor_id=None,  # External system
            details={
                "event_type": event.event_type.value,
                "entity_type": event.entity_type,
                "source": "pipedrive",
            },
        )
        
        return {"status": "processed", "event_type": event.event_type.value}
        
    except json.JSONDecodeError as e:
        logger.error(
            "webhook_json_parse_error",
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )
    except Exception as e:
        logger.error(
            "webhook_processing_error",
            error=str(e),
            exc_info=True,
        )
        # Return 200 to prevent Pipedrive from retrying
        # (log error for manual review)
        return {"status": "error", "message": str(e)}


async def process_webhook_event(event: Any, db: AsyncSession, audit: AuditService):
    """
    Process a Pipedrive webhook event.
    
    Args:
        event: Parsed webhook event
        db: Database session
        audit: Audit service
    """
    customers_repo = CustomersRepository(db)
    
    # Handle organization events
    if event.entity_type == "organization":
        if event.event_type.value in ["added", "updated"]:
            # Check if customer exists with this Pipedrive org ID
            customers, _ = await customers_repo.list_all()
            matching_customer = None
            
            for customer in customers:
                external_ids = customer.external_ids or {}
                if external_ids.get("pipedrive_org_id") == event.entity_id:
                    matching_customer = customer
                    break
            
            if matching_customer:
                # Update existing customer
                data = event.data or {}
                update_data = {}
                
                if data.get("name"):
                    update_data["name"] = data["name"]
                if data.get("address"):
                    update_data["address"] = data["address"]
                
                if update_data:
                    from app.domain.dto import CustomerUpdate
                    await customers_repo.update(
                        matching_customer.id,
                        CustomerUpdate(**update_data),
                    )
                    
                    logger.info(
                        "customer_updated_from_webhook",
                        customer_id=matching_customer.id,
                        pipedrive_org_id=event.entity_id,
                    )
            else:
                # Create new customer
                data = event.data or {}
                if data.get("name") and data.get("address"):
                    from app.domain.dto import CustomerCreate
                    
                    # Try to extract email from owner data or use placeholder
                    email = data.get("owner_email") or f"pipedrive_{event.entity_id}@example.com"
                    
                    new_customer = await customers_repo.create(
                        CustomerCreate(
                            name=data["name"],
                            email=email,
                            phone=data.get("phone"),
                            address=data["address"],
                        )
                    )
                    
                    # Update with Pipedrive ID
                    await customers_repo.update_external_id(
                        new_customer.id,
                        {"pipedrive_org_id": event.entity_id},
                    )
                    
                    logger.info(
                        "customer_created_from_webhook",
                        customer_id=new_customer.id,
                        pipedrive_org_id=event.entity_id,
                    )
        
        elif event.event_type.value == "deleted":
            # Find and soft-delete customer
            customers, _ = await customers_repo.list_all()
            
            for customer in customers:
                external_ids = customer.external_ids or {}
                if external_ids.get("pipedrive_org_id") == event.entity_id:
                    # Note: Consider whether to actually delete or just log
                    logger.info(
                        "customer_deleted_in_pipedrive",
                        customer_id=customer.id,
                        pipedrive_org_id=event.entity_id,
                    )
                    break
    
    # Handle person events
    elif event.entity_type == "person":
        if event.event_type.value in ["added", "updated"]:
            data = event.data or {}
            
            # Try to find customer by email
            email = None
            if data.get("email"):
                if isinstance(data["email"], list) and len(data["email"]) > 0:
                    email = data["email"][0].get("value")
                elif isinstance(data["email"], str):
                    email = data["email"]
            
            if email:
                customer = await customers_repo.get_by_email(email)
                
                if customer:
                    # Update external IDs
                    external_ids = customer.external_ids or {}
                    if event.entity_id and external_ids.get("pipedrive_person_id") != event.entity_id:
                        external_ids["pipedrive_person_id"] = event.entity_id
                        await customers_repo.update_external_id(customer.id, external_ids)
                        
                        logger.info(
                            "customer_person_id_updated",
                            customer_id=customer.id,
                            pipedrive_person_id=event.entity_id,
                        )
    
    # Handle deal events (for future implementation)
    elif event.entity_type == "deal":
        logger.info(
            "deal_event_received",
            event_type=event.event_type.value,
            deal_id=event.entity_id,
        )
        # TODO: Implement deal synchronization
        # Could create notes, tasks, or tracking records
    
    else:
        logger.debug(
            "unhandled_webhook_event",
            entity_type=event.entity_type,
            event_type=event.event_type.value,
        )
