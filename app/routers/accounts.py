"""
MT5 account management router.

Provides endpoints for creating and managing MetaTrader 5 accounts.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user_id, require_role, get_mt5_manager, get_audit_service
from app.domain.dto import (
    MT5AccountCreate,
    MT5AccountResponse,
    MT5AccountUpdate,
    MT5AccountPasswordReset,
    MT5AccountMoveGroup,
    PaginatedResponse,
)
from app.domain.enums import UserRole, MT5AccountStatus
from app.domain.models import MT5Account
from app.repositories.accounts_repo import AccountsRepository
from app.repositories.customers_repo import CustomersRepository
from app.services.mt5_manager import MT5ManagerService
from app.services.audit import AuditService
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/accounts",
    tags=["MT5 Accounts"],
)


@router.get("", response_model=PaginatedResponse[MT5AccountResponse])
async def list_accounts(
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    status: Optional[MT5AccountStatus] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
) -> PaginatedResponse[MT5AccountResponse]:
    """List MT5 accounts with pagination and filtering."""
    repo = AccountsRepository(db)
    skip = (page - 1) * size
    
    if customer_id:
        accounts = await repo.get_by_customer(customer_id)
        total = len(accounts)
        accounts = accounts[skip:skip + size]
    else:
        accounts, total = await repo.list_all(skip=skip, limit=size, status=status)
    
    return PaginatedResponse(
        items=[MT5AccountResponse.model_validate(acc) for acc in accounts],
        total=total,
        skip=skip,
        limit=size,
    )


@router.post("", response_model=MT5AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    account_data: MT5AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(UserRole.DEALER)),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
    audit: AuditService = Depends(get_audit_service),
) -> MT5AccountResponse:
    """Create a new MT5 trading account."""
    # Validate customer exists
    customers_repo = CustomersRepository(db)
    customer = await customers_repo.get_by_id(account_data.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Create account on MT5 server
    mt5_account = await mt5.create_account(
        group=account_data.group,
        leverage=account_data.leverage,
        currency=account_data.currency,
        password=account_data.password,
        name=customer.name or "",
    )
    
    # Save to database
    accounts_repo = AccountsRepository(db)
    account = await accounts_repo.create(
        customer_id=account_data.customer_id,
        login=mt5_account.login,
        group=account_data.group,
        leverage=account_data.leverage,
        currency=account_data.currency,
        status=MT5AccountStatus.ACTIVE,
        balance=mt5_account.balance,
        credit=mt5_account.credit,
    )
    
    # Create response BEFORE commit to avoid circular relationship issues
    response = MT5AccountResponse(
        id=account.id,
        customer_id=account.customer_id,
        login=account.login,
        group=account.group,
        leverage=account.leverage,
        currency=account.currency,
        status=account.status,
        balance=account.balance,
        credit=account.credit,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )
    
    await db.commit()
    
    # Log audit (after commit)
    await audit.log_account_create(
        actor_id=current_user.id,
        account_id=account.id,
        account_data={"login": account.login, "group": account.group},
    )
    
    logger.info("account_created", login=account.login, customer_id=account_data.customer_id)
    
    return response


@router.get("/{login}", response_model=MT5AccountResponse)
async def get_account(
    login: int,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
) -> MT5AccountResponse:
    """Get MT5 account details by login."""
    repo = AccountsRepository(db)
    account = await repo.get_by_login(login)
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Get live balance from MT5
    try:
        mt5_info = await mt5.get_account_info(login)
        account.balance = mt5_info.balance
        account.credit = mt5_info.credit
    except Exception as e:
        logger.warning("could_not_fetch_mt5_balance", login=login, error=str(e))
    
    return MT5AccountResponse.model_validate(account)


@router.post("/{login}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    login: int,
    password_data: MT5AccountPasswordReset,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(UserRole.DEALER)),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    """Reset MT5 account password."""
    # Verify account exists
    repo = AccountsRepository(db)
    account = await repo.get_by_login(login)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Reset password on MT5 server
    await mt5.reset_password(login, password_data.new_password)
    
    # Log audit
    await audit.log_password_reset(actor_id=current_user.id, login=login)
    
    logger.info("password_reset", login=login)


@router.post("/{login}/move-group", status_code=status.HTTP_204_NO_CONTENT)
async def move_group(
    login: int,
    group_data: MT5AccountMoveGroup,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(UserRole.DEALER)),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    """Move account to different group."""
    # Verify account exists
    repo = AccountsRepository(db)
    account = await repo.get_by_login(login)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    old_group = account.group
    
    # Move on MT5 server
    await mt5.move_to_group(login, group_data.new_group)
    
    # Update database
    await repo.update_group(login, group_data.new_group)
    await db.commit()
    
    # Log audit
    await audit.log(
        actor_id=current_user.id,
        action="group_move",  # Must match AuditAction.GROUP_MOVE value
        entity="mt5_account",
        entity_id=login,
        before={"group": old_group},
        after={"group": group_data.new_group},
    )
    
    logger.info("group_changed", login=login, old_group=old_group, new_group=group_data.new_group)
