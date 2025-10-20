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
from app.domain.enums import AuditAction, UserRole
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
    "/by-agent/{agent_id}",
    response_model=PaginatedResponse[CustomerResponse],
    summary="Get customers by agent",
    description="Get paginated list of customers for a specific agent",
)
async def get_customers_by_agent(
    agent_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Number of records to return"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
) -> PaginatedResponse[CustomerResponse]:
    """
    Get all customers for a specific agent.
    
    - Returns paginated results
    - Requires authentication
    """
    repo = CustomersRepository(db)
    items, total = await repo.get_by_agent(agent_id, skip=skip, limit=limit)
    
    return PaginatedResponse(
        items=[CustomerResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
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
    current_user = Depends(require_role(UserRole.DEALER)),
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
    customer = await repo.create(
        name=customer_data.name,
        email=customer_data.email,
        phone=customer_data.phone,
        address=customer_data.address,
        agent_id=customer_data.agent_id,
        tags=customer_data.tags,
        metadata=customer_data.meta_data,
    )
    
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
        if org_id:
            await repo.update_external_id(customer.id, "pipedrive_org_id", str(org_id))
        if person_id:
            await repo.update_external_id(customer.id, "pipedrive_person_id", str(person_id))
        
        # Refresh customer to get updated external_ids
        if org_id or person_id:
            customer = await repo.get_by_id(customer.id)
        
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
        actor_id=current_user.id,
        customer_id=customer.id,
        customer_data={"name": customer.name, "email": customer.email, "phone": customer.phone, "address": customer.address},
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


@router.get(
    "/{customer_id}/positions",
    summary="Get customer positions",
    description="Get all MT5 positions for a customer across all their accounts",
)
async def get_customer_positions(
    customer_id: int,
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    Get all positions for a customer across all their MT5 accounts.
    
    - Returns net positions aggregated by symbol
    - Includes account-level breakdown
    - Requires authentication
    """
    from app.repositories.accounts_repo import AccountsRepository
    from app.services.positions import PositionsService
    
    # Verify customer exists
    customers_repo = CustomersRepository(db)
    customer = await customers_repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID {customer_id} not found",
        )
    
    # Get all MT5 accounts for this customer
    accounts_repo = AccountsRepository(db)
    accounts = await accounts_repo.get_by_customer(customer_id)
    
    if not accounts:
        return {
            "customer_id": customer_id,
            "customer_name": customer.name,
            "accounts": [],
            "net_positions": [],
            "total_volume": 0.0,
            "total_profit": 0.0,
        }
    
    # Get positions service
    positions_service = PositionsService()
    
    # Collect positions from all accounts
    all_positions = []
    account_summaries = []
    
    for account in accounts:
        try:
            # Get positions for this account
            positions = await positions_service.get_open_positions(
                login=account.login,
                symbol=symbol
            )
            
            # Calculate account summary
            account_volume = sum(p.get("volume", 0) for p in positions)
            account_profit = sum(p.get("profit", 0) for p in positions)
            
            account_summaries.append({
                "login": account.login,
                "group": account.group,
                "currency": account.currency,
                "positions_count": len(positions),
                "total_volume": account_volume,
                "total_profit": account_profit,
                "positions": positions,
            })
            
            all_positions.extend(positions)
        except Exception as e:
            logger.error(
                "failed_to_get_positions_for_account",
                customer_id=customer_id,
                login=account.login,
                error=str(e),
            )
    
    # Calculate net positions by symbol
    symbol_net = {}
    for pos in all_positions:
        symbol_name = pos.get("symbol", "UNKNOWN")
        volume = pos.get("volume", 0)
        profit = pos.get("profit", 0)
        action = pos.get("action", 0)  # 0=buy, 1=sell
        
        if symbol_name not in symbol_net:
            symbol_net[symbol_name] = {
                "symbol": symbol_name,
                "buy_volume": 0.0,
                "sell_volume": 0.0,
                "net_volume": 0.0,
                "total_profit": 0.0,
                "positions_count": 0,
            }
        
        if action == 0:  # Buy
            symbol_net[symbol_name]["buy_volume"] += volume
        else:  # Sell
            symbol_net[symbol_name]["sell_volume"] += volume
        
        symbol_net[symbol_name]["net_volume"] = (
            symbol_net[symbol_name]["buy_volume"] - symbol_net[symbol_name]["sell_volume"]
        )
        symbol_net[symbol_name]["total_profit"] += profit
        symbol_net[symbol_name]["positions_count"] += 1
    
    net_positions = list(symbol_net.values())
    total_volume = sum(abs(p["net_volume"]) for p in net_positions)
    total_profit = sum(p["total_profit"] for p in net_positions)
    
    return {
        "customer_id": customer_id,
        "customer_name": customer.name,
        "accounts": account_summaries,
        "net_positions": net_positions,
        "total_volume": total_volume,
        "total_profit": total_profit,
        "positions_count": len(all_positions),
    }


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
    current_user = Depends(require_role(UserRole.DEALER)),
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
    before_data = {}
    after_data = {}
    for field, new_value in customer_data.model_dump(exclude_unset=True).items():
        old_value = getattr(customer, field)
        if old_value != new_value:
            before_data[field] = old_value
            after_data[field] = new_value
            # Update the customer object
            setattr(customer, field, new_value)
    
    # Update in database
    updated_customer = await repo.update(customer)
    
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
            if org_id:
                await repo.update_external_id(customer_id, "pipedrive_org_id", str(org_id))
            if person_id:
                await repo.update_external_id(customer_id, "pipedrive_person_id", str(person_id))
            
            # Refresh the updated customer to get the latest external_ids
            updated_customer = await repo.get_by_id(customer_id)
        
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
    if before_data:  # Only log if there were actual changes
        await audit.log_customer_update(
            actor_id=current_user.id,
            customer_id=customer_id,
            before_data=before_data,
            after_data=after_data,
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
    current_user = Depends(require_role(UserRole.ADMIN)),
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
    
    # Delete customer
    await repo.delete(customer)
    
    # Audit log
    await audit.log(
        action=AuditAction.DELETE,
        entity="customer",
        entity_id=customer_id,
        actor_id=current_user.id,
        before={"name": customer.name, "email": customer.email},
    )
    
    logger.info("customer_deleted", customer_id=customer_id, actor_id=current_user.id)
