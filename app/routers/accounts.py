"""
MT5 account management router.

Provides endpoints for creating and managing MetaTrader 5 accounts.
"""
from datetime import date
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
    MT5GroupResponse,
    MT5DailyReportResponse,
    MT5DailyPnLResponse,
    MT5RealtimeEquityResponse,
    MT5DealHistoryResponse,
    MT5TradeHistoryResponse,
    OpenPosition,
    PaginatedResponse,
)
from app.domain.enums import UserRole, MT5AccountStatus
from app.domain.models import MT5Account
from app.repositories.accounts_repo import AccountsRepository
from app.repositories.customers_repo import CustomersRepository
from app.services.mt5_manager import MT5ManagerService
from app.services.audit import AuditService
from app.services.daily_pnl import DailyPnLService
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
    refresh_balance: bool = Query(False, description="Fetch live balance from MT5"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
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
    
    # Optionally refresh balance from MT5
    if refresh_balance:
        for account in accounts:
            try:
                mt5_info = await mt5.get_account_info(account.login)
                account.balance = mt5_info.balance
                account.credit = mt5_info.credit
            except Exception as e:
                logger.warning("could_not_fetch_mt5_balance", login=account.login, error=str(e))
    
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
    customers_repo = CustomersRepository(db)
    
    # Determine or create customer
    if account_data.customer_id:
        # Use existing customer
        customer = await customers_repo.get_by_id(account_data.customer_id)
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
    elif account_data.customer_name:
        # Auto-create customer from provided data
        if not account_data.agent_id:
            raise HTTPException(
                status_code=400, 
                detail="agent_id is required when creating a new customer"
            )
        
        # Check if customer with same email already exists
        if account_data.customer_email:
            existing = await customers_repo.get_by_email(account_data.customer_email)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Customer with email {account_data.customer_email} already exists",
                )
        
        customer = await customers_repo.create(
            name=account_data.customer_name,
            email=account_data.customer_email,
            phone=account_data.customer_phone,
            agent_id=account_data.agent_id,
        )
        logger.info("customer_auto_created", customer_id=customer.id, agent_id=account_data.agent_id)
    else:
        raise HTTPException(
            status_code=400, 
            detail="Either customer_id or customer_name must be provided"
        )
    
    # Create account on MT5 server
    # Use provided name or fall back to customer name
    display_name = account_data.name or customer.name or ""
    mt5_account = await mt5.create_account(
        group=account_data.group,
        leverage=account_data.leverage,
        currency=account_data.currency,
        password=account_data.password,
        name=display_name,
    )
    
    # Save to database
    accounts_repo = AccountsRepository(db)
    account = await accounts_repo.create(
        customer_id=customer.id,
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
    
    logger.info("account_created", login=account.login, customer_id=customer.id)
    
    return response


@router.get(
    "/groups",
    response_model=list[MT5GroupResponse],
    summary="Get MT5 Groups",
    description="Get all available MT5 groups from the trading server",
)
async def get_mt5_groups(
    mt5: MT5ManagerService = Depends(get_mt5_manager),
    current_user_id: int = Depends(get_current_user_id),
) -> list[MT5GroupResponse]:
    """
    Get all MT5 groups.
    
    Returns a list of available groups from the MetaTrader 5 server.
    Useful for populating group selection dropdowns.
    """
    try:
        logger.info("get_groups_requested", user_id=current_user_id)
        groups = await mt5.get_groups()
        logger.info("groups_fetched", count=len(groups), user_id=current_user_id)
        
        # Convert to DTO
        response = []
        for group in groups:
            try:
                group_dto = MT5GroupResponse(**group)
                response.append(group_dto)
            except Exception as e:
                logger.error("group_dto_conversion_failed", group=group, error=str(e))
                continue
        
        logger.info("groups_response_prepared", count=len(response))
        return response
    except Exception as e:
        logger.error("get_groups_failed", error=str(e), error_type=type(e).__name__, user_id=current_user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch MT5 groups: {str(e)}"
        )


@router.get("/daily-reports", response_model=list[MT5DailyReportResponse])
async def get_daily_reports(
    login: Optional[int] = Query(None, description="Specific account login (returns all if not provided)"),
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD, defaults to yesterday)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD, defaults to today)"),
    group: Optional[str] = Query(None, description="Group filter pattern (e.g., 'demo\\*')"),
    current_user_id: int = Depends(get_current_user_id),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
) -> list[MT5DailyReportResponse]:
    """
    Get comprehensive daily reports with complete MT5 account data.
    
    This endpoint retrieves daily snapshots of account states from MT5's DailyRequestLightByGroupAll method, including:
    
    **Account State:**
    - Balance, Credit, Margin, Margin Free, Margin Level, Leverage
    - Equity (current and previous day/month)
    - Floating Profit/Loss
    
    **Daily Transaction Breakdown:**
    - Balance operations (deposits/withdrawals)
    - Credit operations, Corrections, Bonuses
    - Commissions (fees, instant, round)
    - Interest, Dividends, Taxes
    - Closed Profit, Storage/Swap
    - Stop-out compensations
    
    **Agent & Commission Data:**
    - Daily and monthly agent commissions
    - Daily and monthly commissions
    
    **Profit Analysis:**
    - Equity profit (floating)
    - Storage profit
    - Assets and Liabilities profit
    
    **Account Info:**
    - Name, Email, Company, Group, Currency
    
    **Examples:**
    - Get yesterday's report for all accounts: `GET /api/accounts/daily-reports`
    - Get specific account for a date range: `GET /api/accounts/daily-reports?login=350001&from_date=2025-10-01&to_date=2025-10-16`
    - Get all accounts in a group: `GET /api/accounts/daily-reports?group=demo\\*&from_date=2025-10-15`
    
    **Note:** Reports are generated at end-of-day (EOD) by MT5 server and contain all available fields from the MT5 API.
    """
    try:
        # Parse date strings to date objects
        parsed_from_date = None
        parsed_to_date = None
        
        if from_date:
            try:
                parsed_from_date = date.fromisoformat(from_date)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid from_date format. Expected YYYY-MM-DD, got: {from_date}"
                )
        
        if to_date:
            try:
                parsed_to_date = date.fromisoformat(to_date)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid to_date format. Expected YYYY-MM-DD, got: {to_date}"
                )
        
        reports = await mt5.get_daily_reports(
            login=login,
            from_date=parsed_from_date,
            to_date=parsed_to_date,
            group=group,
        )
        
        result = [
            MT5DailyReportResponse(
                login=report.login,
                date=report.date,
                balance=report.balance,
                credit=report.credit,
                equity_prev_day=report.equity_prev_day,
                equity_prev_month=report.equity_prev_month,
                balance_prev_day=report.balance_prev_day,
                balance_prev_month=report.balance_prev_month,
                margin=report.margin,
                margin_free=report.margin_free,
                margin_level=report.margin_level,
                margin_leverage=report.margin_leverage,
                floating_profit=report.floating_profit,
                group=report.group,
                currency=report.currency,
                currency_digits=report.currency_digits,
                timestamp=report.timestamp,
                datetime_prev=report.datetime_prev,
                
                # Account info
                name=report.name,
                email=report.email,
                company=report.company,
                
                # Agent commissions
                agent_daily=report.agent_daily,
                agent_monthly=report.agent_monthly,
                commission_daily=report.commission_daily,
                commission_monthly=report.commission_monthly,
                
                # Daily transactions breakdown
                daily_balance=report.daily_balance,
                daily_credit=report.daily_credit,
                daily_charge=report.daily_charge,
                daily_correction=report.daily_correction,
                daily_bonus=report.daily_bonus,
                daily_comm_fee=report.daily_comm_fee,
                daily_comm_instant=report.daily_comm_instant,
                daily_comm_round=report.daily_comm_round,
                daily_interest=report.daily_interest,
                daily_dividend=report.daily_dividend,
                daily_profit=report.daily_profit,
                daily_storage=report.daily_storage,
                daily_agent=report.daily_agent,
                daily_so_compensation=report.daily_so_compensation,
                daily_so_compensation_credit=report.daily_so_compensation_credit,
                daily_taxes=report.daily_taxes,
                
                # Interest rate
                interest_rate=report.interest_rate,
                
                # Profit breakdown
                present_equity=report.present_equity,
                profit_storage=report.profit_storage,
                profit_assets=report.profit_assets,
                profit_liabilities=report.profit_liabilities,
            )
            for report in reports
        ]
        
        logger.info("daily_reports_retrieved", 
                   login=login, 
                   from_date=from_date, 
                   to_date=to_date,
                   group=group,
                   total_reports=len(result))
        
        return result
        
    except Exception as e:
        logger.error("daily_reports_failed", 
                    login=login, 
                    from_date=from_date, 
                    to_date=to_date,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch daily reports: {str(e)}"
        )


@router.get("/daily-pnl", response_model=MT5DailyPnLResponse)
async def get_daily_pnl(
    login: int = Query(..., description="Account login"),
    target_date: str = Query(..., description="Target date (YYYY-MM-DD, e.g., 2025-10-31)"),
    current_user_id: int = Depends(get_current_user_id),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
) -> MT5DailyPnLResponse:
    """
    Calculate daily PNL for a specific account and date.
    
    **Formula:** equity_pnl = present_equity - equity_prev_day - net_deposit - net_credit_promotion - total_ib
    
    **Process:**
    - For target date (e.g., 31.10), fetches daily reports from 30.10 to 31.10
    - Uses 31.10 present_equity and equity_prev_day from the report
    - Calculates net_deposit from deposits/withdrawals on 31.10
    - Calculates net_credit_promotion from credits/bonuses on 31.10
    - Gets total_ib from daily_agent field in the report
    - Sums rebate from REB-tagged deals on 31.10
    
    **Example:**
    - Calculate PNL for Oct 31: `GET /api/accounts/daily-pnl?login=350001&target_date=2025-10-31`
    
    **Returns:**
    - login: Account login
    - date: Target date (YYYY-MM-DD)
    - present_equity: Current day equity
    - equity_prev_day: Previous day equity
    - net_deposit: Net deposits (deposits - withdrawals)
    - net_credit_promotion: Net credit/promotions
    - total_ib: Total IB commissions
    - rebate: Total rebate from REB-tagged deals
    - equity_pnl: Calculated PNL
    - group: Account group
    - currency: Account currency
    """
    try:
        # Parse target date
        try:
            target_date_obj = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format: {target_date}. Use YYYY-MM-DD format."
            )
        
        logger.info("calculating_daily_pnl", login=login, target_date=target_date)
        
        # Create PNL service and calculate
        pnl_service = DailyPnLService(mt5)
        pnl_result = await pnl_service.calculate_daily_pnl(target_date_obj, login)
        
        if not pnl_result:
            raise HTTPException(
                status_code=404,
                detail=f"No data available for login {login} on date {target_date}"
            )
        
        # Map to response DTO
        response = MT5DailyPnLResponse(
            login=pnl_result.login,
            date=pnl_result.date,
            present_equity=pnl_result.present_equity,
            equity_prev_day=pnl_result.equity_prev_day,
            deposit=pnl_result.deposit,
            withdrawal=pnl_result.withdrawal,
            net_deposit=pnl_result.net_deposit,
            promotion=pnl_result.promotion,
            net_credit_promotion=pnl_result.net_credit_promotion,
            total_ib=pnl_result.total_ib,
            rebate=pnl_result.rebate,
            equity_pnl=pnl_result.equity_pnl,
            net_pnl=pnl_result.net_pnl,
            group=pnl_result.group,
            currency=pnl_result.currency,
        )
        
        logger.info("daily_pnl_calculated", 
                   login=login, 
                   target_date=target_date,
                   equity_pnl=pnl_result.equity_pnl)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("daily_pnl_calculation_failed", 
                    login=login, 
                    target_date=target_date,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate daily PNL: {str(e)}"
        )


@router.get("/realtime", response_model=list[MT5RealtimeEquityResponse])
async def get_realtime_accounts(
    login: Optional[int] = Query(None, description="Specific account login (returns all if not provided)"),
    group: Optional[str] = Query(None, description="Group filter pattern (e.g., 'test\\*')"),
    current_user_id: int = Depends(get_current_user_id),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
) -> list[MT5RealtimeEquityResponse]:
    """
    Get realtime account information.
    
    This endpoint fetches **current** (realtime) account states including:
    - Current Balance
    - Credit
    - **Realtime Equity** (Balance + Credit + Current Floating P/L)
    - Current Margin & Margin Free
    - Margin Level
    - Current Floating Profit/Loss
    
    **Examples:**
    - Get all accounts: `GET /api/accounts/realtime`
    - Get specific account: `GET /api/accounts/realtime?login=350004`
    - Get accounts in a group: `GET /api/accounts/realtime?group=test\\*`
    
    **Use Cases:**
    - Display current account equity in dashboards
    - Monitor real-time account status across all accounts
    - Calculate current risk metrics
    - Live portfolio monitoring
    
    **Difference from Daily Reports:**
    - Daily Reports (`/daily-reports`): Historical EOD (end-of-day) snapshots with prev_day comparison
    - Realtime (`/realtime`): Current live account state with floating P/L
    """
    try:
        accounts = await mt5.get_realtime_accounts(login=login, group=group)
        
        # If specific login requested but not found, return 404
        if login is not None and len(accounts) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Account {login} not found"
            )
        
        result = [
            MT5RealtimeEquityResponse(
                login=acc.login,
                name=acc.name,
                balance=acc.balance,
                credit=acc.credit,
                equity=acc.equity,
                net_equity=acc.net_equity,
                margin=acc.margin,
                margin_free=acc.margin_free,
                margin_level=acc.margin_level,
                floating_profit=acc.floating_profit,
                group=acc.group,
                currency=acc.currency,
                timestamp=acc.timestamp,
            )
            for acc in accounts
        ]
        
        logger.info("realtime_accounts_retrieved", 
                   login=login, 
                   group=group, 
                   total=len(result))
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("realtime_accounts_failed", login=login, group=group, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch realtime accounts: {str(e)}"
        )


@router.get("/history/deals", response_model=list[MT5DealHistoryResponse])
async def get_deal_history(
    login: Optional[int] = Query(None, description="Specific account login (returns all if not provided)"),
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD, defaults to 30 days ago)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD, defaults to today)"),
    current_user_id: int = Depends(get_current_user_id),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
) -> list[MT5DealHistoryResponse]:
    """
    Get deposit, withdrawal, and credit history.
    
    This endpoint retrieves balance operation history including:
    - **Deposits** - Money added to account
    - **Withdrawals** - Money removed from account
    - **Credits** - Credit added/removed
    - **Charges** - Fees or charges
    - **Corrections** - Manual balance corrections
    
    **Examples:**
    - Get last 30 days for all accounts: `GET /api/accounts/history/deals`
    - Get specific account history: `GET /api/accounts/history/deals?login=350004`
    - Get date range: `GET /api/accounts/history/deals?login=350004&from_date=2025-10-01&to_date=2025-10-20`
    - Get all accounts in date range: `GET /api/accounts/history/deals?from_date=2025-10-15&to_date=2025-10-20`
    
    **Use Cases:**
    - Transaction history display
    - Deposit/withdrawal tracking
    - Credit management monitoring
    - Financial reporting and auditing
    - Balance verification
    """
    try:
        # Parse date strings
        parsed_from_date = None
        parsed_to_date = None
        
        if from_date:
            try:
                parsed_from_date = date.fromisoformat(from_date)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid from_date format. Expected YYYY-MM-DD, got: {from_date}"
                )
        
        if to_date:
            try:
                parsed_to_date = date.fromisoformat(to_date)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid to_date format. Expected YYYY-MM-DD, got: {to_date}"
                )
        
        # Get deal history from MT5
        deals = await mt5.get_deal_history(
            login=login,
            from_date=parsed_from_date,
            to_date=parsed_to_date,
        )
        
        result = [
            MT5DealHistoryResponse(
                deal_id=deal.deal_id,
                login=deal.login,
                action=deal.action,
                amount=deal.amount,
                balance_after=deal.balance_after,
                comment=deal.comment,
                timestamp=deal.timestamp,
                datetime_str=deal.datetime_str,
            )
            for deal in deals
        ]
        
        logger.info("deal_history_retrieved",
                   login=login,
                   from_date=from_date,
                   to_date=to_date,
                   total=len(result))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("deal_history_failed",
                    login=login,
                    from_date=from_date,
                    to_date=to_date,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch deal history: {str(e)}"
        )


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
    
    # Get live balance and name from MT5
    account_name = None
    try:
        mt5_info = await mt5.get_account_info(login)
        account.balance = mt5_info.balance
        account.credit = mt5_info.credit
        account_name = mt5_info.name
    except Exception as e:
        logger.warning("could_not_fetch_mt5_balance", login=login, error=str(e))
    
    # Convert to response and add name
    response = MT5AccountResponse.model_validate(account)
    if account_name:
        response.name = account_name
    
    return response


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


@router.get("/positions/account/{login}", response_model=list[OpenPosition])
async def get_account_positions(
    login: int,
    symbol_filter: Optional[str] = Query(None, description="Filter by symbol (e.g., 'EURUSD')"),
    current_user_id: int = Depends(get_current_user_id),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
) -> list[OpenPosition]:
    """
    Get open positions for a specific MT5 account.
    
    Returns all open positions with details:
    - Position ticket, symbol, volume
    - Open price, current price, profit
    - Swap and commission
    
    **Example Response:**
    ```json
    [
        {
            "ticket": 12345,
            "login": 350008,
            "symbol": "EURUSD",
            "volume": 0.10,
            "type": "BUY",
            "price_open": 1.09500,
            "price_current": 1.09550,
            "profit": 5.00,
            "swap": -0.50,
            "commission": -2.00
        }
    ]
    ```
    """
    try:
        positions_data = await mt5.get_positions_by_login(login=login, symbol_filter=symbol_filter)
        
        if not positions_data:
            logger.info("no_positions_found", login=login, symbol_filter=symbol_filter)
            return []
        
        result = [
            OpenPosition(
                ticket=pos.get('ticket', 0),
                login=pos.get('login', login),
                symbol=pos.get('symbol', ''),
                volume=pos.get('volume', 0.0),
                type='BUY' if pos.get('action') == 0 else 'SELL',
                price_open=pos.get('price_open', 0.0),
                price_current=pos.get('price_current', 0.0),
                profit=pos.get('profit', 0.0),
                swap=pos.get('swap', 0.0),
                commission=pos.get('commission', 0.0),
            )
            for pos in positions_data
        ]
        
        logger.info("positions_retrieved", login=login, total=len(result))
        return result
        
    except Exception as e:
        logger.error("positions_failed", login=login, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch positions: {str(e)}"
        )


@router.get("/{login}/deal-history", response_model=list[MT5DealHistoryResponse])
async def get_deal_history(
    login: int,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
) -> list[MT5DealHistoryResponse]:
    """
    Get deal history (deposits, withdrawals, credits) for an account.
    
    Returns balance operations like:
    - DEPOSIT: Money added to account
    - WITHDRAWAL: Money removed from account
    - CREDIT: Credit added/removed
    - CHARGE: Commissions, swaps
    - CORRECTION: Balance corrections
    
    Default: Last 30 days of history
    """
    # Verify account exists
    repo = AccountsRepository(db)
    account = await repo.get_by_login(login)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    try:
        # Get all deal history (defaults to last 30 days)
        deals = await mt5.get_deal_history(login=login)
        
        # Convert to response DTOs
        result = [
            MT5DealHistoryResponse(
                deal_id=deal.deal_id,
                login=deal.login,
                action=deal.action,
                amount=deal.amount,
                balance_after=deal.balance_after,
                comment=deal.comment,
                timestamp=deal.timestamp,
                datetime_str=deal.datetime_str,
            )
            for deal in deals
        ]
        
        logger.info("deal_history_retrieved", login=login, total=len(result))
        return result
        
    except Exception as e:
        logger.error("deal_history_failed", login=login, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch deal history: {str(e)}"
        )


@router.get("/{login}/trade-history", response_model=list[MT5TradeHistoryResponse])
async def get_trade_history(
    login: int,
    from_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
) -> list[MT5TradeHistoryResponse]:
    """
    Get trade history (closed positions) for an account.
    
    Returns closed trades with:
    - Symbol traded (e.g., EURUSD, XAUUSD)
    - Action (BUY or SELL)
    - Volume in lots
    - Execution price
    - Profit/Loss
    - Commission and Swap fees
    - Timestamp
    
    Default: Last 30 days if no date range specified
    """
    # Verify account exists
    repo = AccountsRepository(db)
    account = await repo.get_by_login(login)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    try:
        # Get position history (closed positions)
        positions = await mt5.get_position_history(login=login, from_date=from_date, to_date=to_date)
        
        # Convert to response DTOs
        result = [
            MT5TradeHistoryResponse(
                deal_id=pos["deal_id"],
                login=pos["login"],
                symbol=pos["symbol"],
                action=pos["action"],
                volume=pos["volume"],
                price=pos["price"],
                profit=pos["profit"],
                commission=pos["commission"],
                swap=pos["swap"],
                timestamp=pos["timestamp"],
                datetime=pos["datetime"],
            )
            for pos in positions
        ]
        
        logger.info("trade_history_retrieved", login=login, total=len(result), from_date=from_date, to_date=to_date)
        return result
        
    except Exception as e:
        logger.error("trade_history_failed", login=login, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch trade history: {str(e)}"
        )


@router.put("/{login}/group", status_code=status.HTTP_200_OK)
async def change_account_group(
    login: int,
    group_data: MT5AccountMoveGroup,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(UserRole.DEALER)),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
    audit: AuditService = Depends(get_audit_service),
):
    """
    Change account group in MT5.
    
    Moves the account to a different trading group with different:
    - Spreads
    - Commission rates
    - Leverage limits
    - Trading conditions
    """
    # Verify account exists
    repo = AccountsRepository(db)
    account = await repo.get_by_login(login)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    old_group = account.group
    new_group = group_data.new_group
    
    try:
        # Change group in MT5
        await mt5.change_group(login=login, new_group=new_group)
        
        # Update database
        account.group = new_group
        await db.commit()
        
        # Audit log
        await audit.log(
            action="update",
            entity="mt5_account",
            entity_id=account.id,
            before={"group": old_group},
            after={"group": new_group},
        )
        
        logger.info("account_group_changed", login=login, old_group=old_group, new_group=new_group)
        return {"message": f"Account {login} moved to group {new_group}", "old_group": old_group, "new_group": new_group}
        
    except Exception as e:
        logger.error("change_group_failed", login=login, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to change group: {str(e)}"
        )


@router.put("/{login}/password", status_code=status.HTTP_200_OK)
async def change_account_password(
    login: int,
    password_data: MT5AccountPasswordReset,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(UserRole.DEALER)),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
    audit: AuditService = Depends(get_audit_service),
):
    """
    Change main trading password for MT5 account.
    
    This password allows full trading access:
    - Open/close positions
    - Deposit/withdraw
    - View history
    """
    # Verify account exists
    repo = AccountsRepository(db)
    account = await repo.get_by_login(login)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    try:
        # Change password in MT5
        await mt5.change_password(login=login, new_password=password_data.new_password)
        
        # Audit log (don't log the actual password)
        await audit.log(
            action="update",
            entity="mt5_account",
            entity_id=account.id,
            before={"password": "***"},
            after={"password": "***"},
        )
        
        logger.info("account_password_changed", login=login)
        return {"message": f"Password changed successfully for account {login}"}
        
    except Exception as e:
        logger.error("change_password_failed", login=login, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to change password: {str(e)}"
        )


@router.put("/{login}/investor-password", status_code=status.HTTP_200_OK)
async def change_investor_password(
    login: int,
    password_data: MT5AccountPasswordReset,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(UserRole.DEALER)),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
    audit: AuditService = Depends(get_audit_service),
):
    """
    Change investor (read-only) password for MT5 account.
    
    Investor password allows:
    - View positions and history
    - Monitor account performance
    
    Does NOT allow:
    - Trading
    - Deposits/withdrawals
    - Account modifications
    """
    # Verify account exists
    repo = AccountsRepository(db)
    account = await repo.get_by_login(login)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    try:
        # Change investor password in MT5
        await mt5.change_investor_password(login=login, new_password=password_data.new_password)
        
        # Audit log (don't log the actual password)
        await audit.log(
            action="update",
            entity="mt5_account",
            entity_id=account.id,
            before={"investor_password": "***"},
            after={"investor_password": "***"},
        )
        
        logger.info("investor_password_changed", login=login)
        return {"message": f"Investor password changed successfully for account {login}"}
        
    except Exception as e:
        logger.error("change_investor_password_failed", login=login, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to change investor password: {str(e)}"
        )
