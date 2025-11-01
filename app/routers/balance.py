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
    """
    Create a new balance operation (deposit, withdrawal, credit_in, credit_out).
    
    Supports all operation types:
    - deposit: Add funds to account balance
    - withdrawal: Remove funds from account balance
    - credit_in: Add credit (leverage) to account
    - credit_out: Remove credit from account
    """
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
    
    logger.info("balance_operation_created", operation_id=operation.id, login=operation_data.login, type=operation_data.type)
    return BalanceOperationResponse.model_validate(operation)


@router.post("/credit", response_model=BalanceOperationResponse, status_code=status.HTTP_201_CREATED)
async def credit_operation(
    login: int,
    amount: float = Query(..., description="Credit amount (positive for credit_in, negative for credit_out)"),
    comment: Optional[str] = Query(None, description="Operation comment"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(UserRole.DEALER)),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
    audit: AuditService = Depends(get_audit_service),
) -> BalanceOperationResponse:
    """
    Add or remove credit (leverage) from an MT5 account.
    
    - Positive amount: credit_in (add credit)
    - Negative amount: credit_out (remove credit)
    - Requires DEALER role or higher
    - Supports idempotency
    """
    # Determine operation type based on amount sign
    if amount > 0:
        op_type = BalanceOperationType.CREDIT_IN
    elif amount < 0:
        op_type = BalanceOperationType.CREDIT_OUT
        amount = abs(amount)  # Make it positive for storage
    else:
        raise HTTPException(status_code=400, detail="Amount cannot be zero")
    
    repo = BalanceRepository(db)
    
    # Check idempotency
    if idempotency_key:
        existing = await repo.get_by_idempotency_key(idempotency_key)
        if existing:
            return BalanceOperationResponse.model_validate(existing)
    
    # Verify account exists
    accounts_repo = AccountsRepository(db)
    account = await accounts_repo.get_by_login(login)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Apply operation to MT5
    result = await mt5.apply_balance_operation(
        login=login,
        op_type=op_type.value,
        amount=amount,
        comment=comment or f"Credit operation by user {current_user.id}",
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Credit operation failed")
    
    # Save to database
    operation = await repo.create(
        account_id=account.id,
        login=login,
        operation_type=op_type,
        amount=amount,
        comment=comment,
        requested_by=current_user.id,
        idempotency_key=idempotency_key,
    )
    
    operation.status = BalanceOperationStatus.COMPLETED
    await db.commit()
    await db.refresh(operation)
    
    # Log audit
    await audit.log_balance_operation(
        actor_id=current_user.id,
        operation_id=operation.id,
        operation_data={
            "login": login,
            "type": op_type.value,
            "amount": amount,
        },
    )
    
    logger.info("credit_operation_completed", operation_id=operation.id, login=login, type=op_type.value, amount=amount)
    return BalanceOperationResponse.model_validate(operation)


@router.get("/net-deposit")
async def get_net_deposit(
    login: Optional[int] = Query(None, description="Filter by MT5 login"),
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
):
    """
    Get net deposit summary with categorized transactions.
    
    - Filters only DEPOSIT and WITHDRAWAL transactions
    - Categorizes by comment:
      - Comments starting with 'DT' or 'WT' → tagged as 'deposit'
      - Other comments → tagged as 'promotion'
    - Returns summary with totals and categorized transactions
    """
    from datetime import datetime, timedelta
    
    # Parse dates
    if from_date:
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid from_date format. Use YYYY-MM-DD")
    else:
        from_dt = datetime.now() - timedelta(days=30)  # Default: last 30 days
    
    if to_date:
        try:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")
            to_dt = to_dt.replace(hour=23, minute=59, second=59)  # End of day
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid to_date format. Use YYYY-MM-DD")
    else:
        to_dt = datetime.now()
    
    # Get deals from MT5
    deals = await mt5.get_deal_history(
        login=login,
        from_date=from_dt.date(),
        to_date=to_dt.date()
    )
    
    # Filter only DEPOSIT and WITHDRAWAL deals
    filtered_deals = [
        deal for deal in deals 
        if deal.action in ['DEPOSIT', 'WITHDRAWAL']
    ]
    
    # Categorize and aggregate
    deposit_total = 0.0
    withdrawal_total = 0.0
    deposit_tagged = 0.0
    promotion_tagged = 0.0
    withdrawal_tagged = 0.0
    withdrawal_promotion = 0.0
    
    deposit_transactions = []
    withdrawal_transactions = []
    
    for deal in filtered_deals:
        # Determine tag based on comment
        comment = deal.comment or ""
        is_tagged = comment.startswith('DT') or comment.startswith('WT')
        tag = 'deposit' if is_tagged else 'promotion'
        
        transaction = {
            "deal_id": deal.deal_id,
            "login": deal.login,
            "action": deal.action,
            "amount": deal.amount,
            "balance_after": deal.balance_after,
            "comment": deal.comment,
            "tag": tag,
            "datetime": deal.datetime_str,
            "timestamp": deal.timestamp,
        }
        
        if deal.action == 'DEPOSIT':
            deposit_total += deal.amount
            if is_tagged:
                deposit_tagged += deal.amount
            else:
                promotion_tagged += deal.amount
            deposit_transactions.append(transaction)
        else:  # WITHDRAWAL
            withdrawal_total += abs(deal.amount)
            if is_tagged:
                withdrawal_tagged += abs(deal.amount)
            else:
                withdrawal_promotion += abs(deal.amount)
            withdrawal_transactions.append(transaction)
    
    # Calculate net deposit
    net_deposit = deposit_total - withdrawal_total
    net_deposit_tagged = deposit_tagged - withdrawal_tagged
    net_promotion = promotion_tagged - withdrawal_promotion
    
    # Sort by timestamp descending (newest first)
    deposit_transactions.sort(key=lambda x: x["timestamp"], reverse=True)
    withdrawal_transactions.sort(key=lambda x: x["timestamp"], reverse=True)
    
    logger.info("net_deposit_calculated",
               login=login,
               deposits=len(deposit_transactions),
               withdrawals=len(withdrawal_transactions),
               net_deposit=net_deposit)
    
    return {
        "login": login,
        "from_date": from_dt.strftime("%Y-%m-%d"),
        "to_date": to_dt.strftime("%Y-%m-%d"),
        "summary": {
            "total_deposits": deposit_total,
            "total_withdrawals": withdrawal_total,
            "net_deposit": net_deposit,
            "deposits_tagged": deposit_tagged,
            "deposits_promotion": promotion_tagged,
            "withdrawals_tagged": withdrawal_tagged,
            "withdrawals_promotion": withdrawal_promotion,
            "net_deposit_tagged": net_deposit_tagged,
            "net_promotion": net_promotion,
        },
        "deposits": {
            "count": len(deposit_transactions),
            "total": deposit_total,
            "transactions": deposit_transactions[:50],  # Limit to 50 most recent
        },
        "withdrawals": {
            "count": len(withdrawal_transactions),
            "total": withdrawal_total,
            "transactions": withdrawal_transactions[:50],  # Limit to 50 most recent
        },
    }
