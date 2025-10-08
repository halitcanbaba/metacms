"""
Customer management router.

Provides CRUD operations for customers with automatic Pipedrive synchronization.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user_id, require_role, get_pipedrive_client, get_audit_service
from app.domain.dto import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    PaginatedResponse,
)
from app.domain.enums import UserRole
from app.domain.models import Customer
from app.repositories.customers_repo import CustomersRepository
from app.services.audit import AuditService
from app.services.pipedrive import PipedriveClient
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/customers",
    tags=["customers"],
)


@router.get(
    "",
    response_model=PaginatedResponse[CustomerResponse],
    summary="List customers",
    description="Get paginated list of customers with optional search",
)
async def list_customers(
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Number of records to return"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
) -> PaginatedResponse[CustomerResponse]:
    """
    List customers with optional search and pagination.
    
    - Supports search across name, email, and phone fields
    - Returns paginated results
    - Requires authentication
    """
    repo = CustomersRepository(db)
    
    if search:
        items, total = await repo.search(search, skip=skip, limit=limit)
    else:
        items, total = await repo.list_all(skip=skip, limit=limit)
    
    return PaginatedResponse(
        items=[CustomerResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create customer",
    description="Create a new customer and sync to Pipedrive",
)
async def create_customer(
    customer_data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(require_role(UserRole.DEALER)),
    pipedrive: PipedriveClient = Depends(get_pipedrive_client),
    audit: AuditService = Depends(get_audit_service),
) -> CustomerResponse:
    """
    Create a new customer.
    
    - Automatically syncs to Pipedrive as organization and person
    - Requires DEALER role or higher
    - Records audit log
    """
    repo = CustomersRepository(db)
    
    # Check if customer with same email already exists
    existing = await repo.get_by_email(customer_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Customer with email {customer_data.email} already exists",
        )
    
    # Create customer in database
    customer = await repo.create(customer_data)
    
    # Sync to Pipedrive (non-blocking - errors are logged but don't fail request)
    try:
        # Create/update organization
        org_id = await pipedrive.upsert_organization(
            name=customer_data.name,
            address=customer_data.address,
            phone=customer_data.phone,
        )
        
        # Create/update person
        person_id = await pipedrive.upsert_person(
            name=customer_data.name,
            email=customer_data.email,
            phone=customer_data.phone,
            org_id=org_id,
        )
        
        # Update customer with external IDs
        if org_id or person_id:
            external_ids = {}
            if org_id:
                external_ids["pipedrive_org_id"] = org_id
            if person_id:
                external_ids["pipedrive_person_id"] = person_id
            
            await repo.update_external_id(customer.id, external_ids)
            customer.external_ids = external_ids
        
        logger.info(
            "customer_synced_to_pipedrive",
            customer_id=customer.id,
            org_id=org_id,
            person_id=person_id,
        )
    except Exception as e:
        logger.error(
            "pipedrive_sync_failed",
            customer_id=customer.id,
            error=str(e),
            exc_info=True,
        )
        # Continue - customer is created, sync can be retried later
    
    # Audit log
    await audit.log_customer_create(
        actor_id=current_user_id,
        customer_id=customer.id,
        details={"name": customer.name, "email": customer.email},
    )
    
    return CustomerResponse.model_validate(customer)


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get customer",
    description="Get customer details by ID",
)
async def get_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
) -> CustomerResponse:
    """
    Get a single customer by ID.
    
    - Returns customer details
    - Requires authentication
    """
    repo = CustomersRepository(db)
    customer = await repo.get_by_id(customer_id)
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )
    
    return CustomerResponse.model_validate(customer)


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update customer",
    description="Update customer details and sync to Pipedrive",
)
async def update_customer(
    customer_id: int,
    customer_data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(require_role(UserRole.DEALER)),
    pipedrive: PipedriveClient = Depends(get_pipedrive_client),
    audit: AuditService = Depends(get_audit_service),
) -> CustomerResponse:
    """
    Update an existing customer.
    
    - Updates database and syncs to Pipedrive
    - Requires DEALER role or higher
    - Records audit log
    """
    repo = CustomersRepository(db)
    
    # Get existing customer
    customer = await repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )
    
    # If email is changing, check for conflicts
    if customer_data.email and customer_data.email != customer.email:
        existing = await repo.get_by_email(customer_data.email)
        if existing and existing.id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Customer with email {customer_data.email} already exists",
            )
    
    # Track changes for audit
    changes = {}
    for field, new_value in customer_data.model_dump(exclude_unset=True).items():
        old_value = getattr(customer, field)
        if old_value != new_value:
            changes[field] = {"old": old_value, "new": new_value}
    
    # Update in database
    updated_customer = await repo.update(customer_id, customer_data)
    
    # Sync to Pipedrive
    try:
        external_ids = customer.external_ids or {}
        
        # Update organization
        org_id = external_ids.get("pipedrive_org_id")
        if customer_data.name or customer_data.address or customer_data.phone:
            org_id = await pipedrive.upsert_organization(
                name=customer_data.name or customer.name,
                address=customer_data.address or customer.address,
                phone=customer_data.phone or customer.phone,
                external_id=org_id,
            )
        
        # Update person
        person_id = external_ids.get("pipedrive_person_id")
        if customer_data.name or customer_data.email or customer_data.phone:
            person_id = await pipedrive.upsert_person(
                name=customer_data.name or customer.name,
                email=customer_data.email or customer.email,
                phone=customer_data.phone or customer.phone,
                org_id=org_id,
                external_id=person_id,
            )
        
        # Update external IDs if needed
        if org_id or person_id:
            new_external_ids = {}
            if org_id:
                new_external_ids["pipedrive_org_id"] = org_id
            if person_id:
                new_external_ids["pipedrive_person_id"] = person_id
            
            if new_external_ids != external_ids:
                await repo.update_external_id(customer_id, new_external_ids)
                updated_customer.external_ids = new_external_ids
        
        logger.info(
            "customer_updated_in_pipedrive",
            customer_id=customer_id,
            org_id=org_id,
            person_id=person_id,
        )
    except Exception as e:
        logger.error(
            "pipedrive_update_failed",
            customer_id=customer_id,
            error=str(e),
            exc_info=True,
        )
    
    # Audit log
    await audit.log_customer_update(
        actor_id=current_user_id,
        customer_id=customer_id,
        changes=changes,
    )
    
    return CustomerResponse.model_validate(updated_customer)


@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete customer",
    description="Delete a customer (soft delete)",
)
async def delete_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(require_role(UserRole.ADMIN)),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    """
    Delete a customer.
    
    - Performs soft delete (sets deleted flag)
    - Requires ADMIN role
    - Records audit log
    - Does NOT delete from Pipedrive (manual cleanup needed)
    """
    repo = CustomersRepository(db)
    
    # Check if customer exists
    customer = await repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )
    
    # Check if customer has active MT5 accounts
    # TODO: Add check when accounts_repo is available
    
    # Soft delete
    await repo.delete(customer_id)
    
    # Audit log
    await audit.log(
        action="customer_deleted",
        entity_type="customer",
        entity_id=customer_id,
        actor_id=current_user_id,
        details={"name": customer.name, "email": customer.email},
    )
    
    logger.info("customer_deleted", customer_id=customer_id, actor_id=current_user_id)
