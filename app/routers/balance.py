"""
Balance operations router.

Provides endpoints for managing balance operations with approval workflow.
"""
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user_id, require_role, get_idempotency_key, get_mt5_manager, get_audit_service
from app.domain.dto import (
    BalanceOperationCreate,
    BalanceOperationResponse,
    PaginatedResponse,
)
from app.domain.enums import UserRole, BalanceOperationStatus, BalanceOperationType
from app.repositories.balance_repo import BalanceRepository
from app.repositories.accounts_repo import AccountsRepository
from app.services.mt5_manager import MT5ManagerService
from app.services.audit import AuditService
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/balance",
    tags=["Balance Operations"],
)


@router.get("", response_model=PaginatedResponse[BalanceOperationResponse])
async def list_operations(
    login: Optional[int] = Query(None, description="Filter by MT5 login"),
    status_filter: Optional[BalanceOperationStatus] = Query(None, alias="status", description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
) -> PaginatedResponse[BalanceOperationResponse]:
    """List balance operations with pagination and filtering."""
    repo = BalanceRepository(db)
    skip = (page - 1) * size
    
    operations, total = await repo.list_all(skip=skip, limit=size, login=login, status=status_filter)
    
    return PaginatedResponse(
        items=[BalanceOperationResponse.model_validate(op) for op in operations],
        total=total,
        skip=skip,
        limit=size,
    )


@router.post("", response_model=BalanceOperationResponse, status_code=status.HTTP_201_CREATED)
async def create_operation(
    operation_data: BalanceOperationCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(UserRole.DEALER)),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
    audit: AuditService = Depends(get_audit_service),
) -> BalanceOperationResponse:
    """Create a new balance operation."""
    repo = BalanceRepository(db)
    
    # Check idempotency
    if idempotency_key:
        existing = await repo.get_by_idempotency_key(idempotency_key)
        if existing:
            return BalanceOperationResponse.model_validate(existing)
    
    # Verify account exists
    accounts_repo = AccountsRepository(db)
    account = await accounts_repo.get_by_login(operation_data.login)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Apply operation to MT5
    result = await mt5.apply_balance_operation(
        login=operation_data.login,
        op_type=operation_data.type if isinstance(operation_data.type, str) else operation_data.type.value,
        amount=operation_data.amount,
        comment=operation_data.comment or "",
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Operation failed")
    
    # Save to database
    operation = await repo.create(
        account_id=account.id,
        login=operation_data.login,
        operation_type=operation_data.type,
        amount=operation_data.amount,
        comment=operation_data.comment,
        requested_by=current_user.id,
        idempotency_key=idempotency_key,
    )
    
    # Mark as completed since we already applied to MT5
    operation.status = BalanceOperationStatus.COMPLETED
    
    await db.commit()
    await db.refresh(operation)
    
    # Log audit
    await audit.log_balance_operation(
        actor_id=current_user.id,
        operation_id=operation.id,
        operation_data={
            "login": operation_data.login,
            "type": operation_data.type if isinstance(operation_data.type, str) else operation_data.type.value,
            "amount": operation_data.amount,
        },
    )
    
    logger.info("balance_operation_created", operation_id=operation.id, login=operation_data.login)
    return BalanceOperationResponse.model_validate(operation)
