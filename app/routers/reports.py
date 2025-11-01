"""
Reports router for daily P&L and other reports.
"""
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user_id
from app.services.daily_pnl import DailyPnLService
from app.services.mt5_manager import MT5ManagerService
from app.repositories.daily_pnl_repo import DailyPnLRepository
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/reports",
    tags=["Reports"],
)


@router.get("/daily-pnl")
async def get_daily_pnl(
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    login: Optional[int] = Query(None, description="Filter by MT5 login"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    Get daily P&L report.
    
    Returns daily P&L metrics including:
    - Deposits and withdrawals (tagged vs promotion)
    - Credits
    - IB costs
    - Trading commission and swap
    - Closed P&L
    - Net P&L
    """
    # Parse dates
    if from_date:
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid from_date format. Use YYYY-MM-DD")
    else:
        from_dt = (datetime.now() - timedelta(days=30)).date()
    
    if to_date:
        try:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid to_date format. Use YYYY-MM-DD")
    else:
        to_dt = datetime.now().date()
    
    # Get from database
    repo = DailyPnLRepository(db)
    records = await repo.get_date_range(from_dt, to_dt, login)
    
    # Convert to response format
    results = []
    for record in records:
        results.append({
            "day": record.day.strftime("%Y-%m-%d") if isinstance(record.day, datetime) else str(record.day),
            "login": record.login,
            "deposit": record.deposit,
            "withdrawal": record.withdrawal,
            "net_deposit": record.net_deposit,
            "promotion": record.promotion,
            "credit": record.credit,
            "net_credit_promotion": record.net_credit_promotion,
            "ib_commission": record.ib_commission,
            "ib_lot_return": record.ib_lot_return,
            "ib_rebate": record.ib_rebate,
            "total_ib": record.total_ib,
            "commission": record.commission,
            "swap": record.swap,
            "closed_pnl": record.closed_pnl,
            "equity_pnl": record.equity_pnl,
            "a_book_pnl": record.a_book_pnl,
            "net_pnl": record.net_pnl,
        })
    
    logger.info("daily_pnl_retrieved",
               from_date=from_dt,
               to_date=to_dt,
               login=login,
               count=len(results))
    
    return {
        "from_date": from_dt.strftime("%Y-%m-%d"),
        "to_date": to_dt.strftime("%Y-%m-%d"),
        "login": login,
        "count": len(results),
        "records": results,
    }


@router.post("/sync-daily-pnl")
async def sync_daily_pnl(
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    login: Optional[int] = Query(None, description="Filter by MT5 login"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    Sync/backfill historical daily P&L data for all accounts or specific account.
    
    **Without login parameter (Recommended):**
    - Calculates PNL for ALL accounts
    - Saves individual records for each account (login > 0)
    - Saves institution aggregate record (login = 0)
    
    **With login parameter:**
    - Calculates PNL only for specified account
    - No institution aggregate is created
    
    **Examples:**
    - All accounts: `POST /api/reports/sync-daily-pnl?from_date=2025-10-01&to_date=2025-10-31`
    - Single account: `POST /api/reports/sync-daily-pnl?login=350001&from_date=2025-10-01&to_date=2025-10-31`
    
    **Response includes:**
    - saved_count: Total records saved (individual + institution aggregate)
    - For all accounts: saved_count = (accounts * days) + days
    """
    # Parse dates
    if from_date:
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid from_date format. Use YYYY-MM-DD")
    else:
        from_dt = (datetime.now() - timedelta(days=30)).date()
    
    if to_date:
        try:
            to_dt = datetime.strptime(to_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid to_date format. Use YYYY-MM-DD")
    else:
        to_dt = datetime.now().date()
    
    logger.info("sync_daily_pnl_started",
               from_date=from_dt,
               to_date=to_dt,
               login=login)
    
    # Calculate P&L for date range
    service = DailyPnLService()
    repo = DailyPnLRepository(db)
    saved_count = 0
    
    if login is not None:
        # Calculate for specific login
        logger.info("calculating_pnl_for_specific_login", login=login)
        pnl_list = await service.calculate_date_range(from_dt, to_dt, login)
        
        # Save individual account records
        for pnl in pnl_list:
            try:
                metrics_dict = {
                    "day": datetime.strptime(pnl.date, "%Y-%m-%d").date(),
                    "login": pnl.login,
                    "deposit": 0.0,
                    "withdrawal": 0.0,
                    "net_deposit": pnl.net_deposit,
                    "promotion": pnl.promotion,
                    "credit": pnl.credit,
                    "net_credit_promotion": pnl.net_credit_promotion,
                    "ib_commission": pnl.total_ib,
                    "ib_lot_return": 0.0,
                    "ib_rebate": pnl.rebate,
                    "total_ib": pnl.total_ib,
                    "commission": 0.0,
                    "swap": 0.0,
                    "closed_pnl": 0.0,
                    "equity_pnl": pnl.equity_pnl,
                    "a_book_pnl": 0.0,
                    "net_pnl": pnl.net_pnl,
                }
                await repo.create_or_update(metrics_dict)
                saved_count += 1
            except Exception as e:
                logger.error("failed_to_save_daily_pnl",
                            date=pnl.date,
                            login=pnl.login,
                            error=str(e))
                continue
    else:
        # Calculate for ALL logins and save both individual + institution aggregate
        logger.info("calculating_pnl_for_all_logins")
        current_date = from_dt
        
        while current_date <= to_dt:
            try:
                # Calculate PNL for all accounts on this date
                all_pnl = await service.calculate_all_logins_pnl(current_date)
                
                # Save individual account records
                for pnl in all_pnl:
                    try:
                        metrics_dict = {
                            "day": datetime.strptime(pnl.date, "%Y-%m-%d").date(),
                            "login": pnl.login,
                            "deposit": pnl.deposit,
                            "withdrawal": pnl.withdrawal,
                            "net_deposit": pnl.net_deposit,
                            "promotion": pnl.promotion,
                            "credit": pnl.credit,
                            "net_credit_promotion": pnl.net_credit_promotion,
                            "ib_commission": pnl.total_ib,
                            "ib_lot_return": 0.0,
                            "ib_rebate": pnl.rebate,
                            "total_ib": pnl.total_ib,
                            "commission": 0.0,
                            "swap": 0.0,
                            "closed_pnl": 0.0,
                            "equity_pnl": pnl.equity_pnl,
                            "a_book_pnl": 0.0,
                            "net_pnl": pnl.net_pnl,
                        }
                        await repo.create_or_update(metrics_dict)
                        saved_count += 1
                    except Exception as e:
                        logger.error("failed_to_save_individual_pnl",
                                    date=pnl.date,
                                    login=pnl.login,
                                    error=str(e))
                        continue
                
                # Calculate and save institution aggregate (login=0)
                institution_pnl = service.aggregate_institution_pnl(all_pnl, current_date)
                try:
                    institution_dict = {
                        "day": datetime.strptime(institution_pnl.date, "%Y-%m-%d").date(),
                        "login": 0,  # 0 = institution total
                        "deposit": institution_pnl.deposit,
                        "withdrawal": institution_pnl.withdrawal,
                        "net_deposit": institution_pnl.net_deposit,
                        "promotion": institution_pnl.promotion,
                        "credit": institution_pnl.credit,
                        "net_credit_promotion": institution_pnl.net_credit_promotion,
                        "ib_commission": institution_pnl.total_ib,
                        "ib_lot_return": 0.0,
                        "ib_rebate": institution_pnl.rebate,
                        "total_ib": institution_pnl.total_ib,
                        "commission": 0.0,
                        "swap": 0.0,
                        "closed_pnl": 0.0,
                        "equity_pnl": institution_pnl.equity_pnl,
                        "a_book_pnl": 0.0,
                        "net_pnl": institution_pnl.net_pnl,
                    }
                    await repo.create_or_update(institution_dict)
                    saved_count += 1
                    logger.info("institution_aggregate_saved",
                               date=current_date,
                               total_accounts=len(all_pnl),
                               total_equity_pnl=institution_pnl.equity_pnl,
                               total_net_pnl=institution_pnl.net_pnl)
                except Exception as e:
                    logger.error("failed_to_save_institution_aggregate",
                                date=current_date,
                                error=str(e))
                
            except Exception as e:
                logger.error("failed_to_calculate_pnl_for_date",
                            date=current_date,
                            error=str(e))
            
            current_date += timedelta(days=1)
    
    logger.info("sync_daily_pnl_completed",
               from_date=from_dt,
               to_date=to_dt,
               login=login,
               saved_count=saved_count,
               total_days=(to_dt - from_dt).days + 1)
    
    return {
        "success": True,
        "from_date": from_dt.strftime("%Y-%m-%d"),
        "to_date": to_dt.strftime("%Y-%m-%d"),
        "login": login,
        "total_days": (to_dt - from_dt).days + 1,
        "saved_count": saved_count,
        "message": f"Successfully synced {saved_count} daily P&L records"
    }


@router.get("/daily-pnl/latest")
async def get_latest_daily_pnl(
    days: int = Query(30, ge=1, le=365, description="Number of days to retrieve"),
    login: Optional[int] = Query(None, description="Filter by MT5 login"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """Get latest daily P&L records."""
    repo = DailyPnLRepository(db)
    records = await repo.get_latest(limit=days, login=login)
    
    results = []
    for record in records:
        results.append({
            "day": record.day.strftime("%Y-%m-%d") if isinstance(record.day, datetime) else str(record.day),
            "login": record.login,
            "deposit": record.deposit,
            "withdrawal": record.withdrawal,
            "net_deposit": record.net_deposit,
            "promotion": record.promotion,
            "credit": record.credit,
            "net_credit_promotion": record.net_credit_promotion,
            "ib_commission": record.ib_commission,
            "ib_lot_return": record.ib_lot_return,
            "ib_rebate": record.ib_rebate,
            "total_ib": record.total_ib,
            "commission": record.commission,
            "swap": record.swap,
            "closed_pnl": record.closed_pnl,
            "equity_pnl": record.equity_pnl,
            "a_book_pnl": record.a_book_pnl,
            "net_pnl": record.net_pnl,
        })
    
    return {
        "login": login,
        "count": len(results),
        "records": results,
    }


@router.get("/monthly-top-winners")
async def get_monthly_top_winners(
    year: Optional[int] = Query(None, description="Year (defaults to current year)"),
    month: Optional[int] = Query(None, description="Month (1-12, defaults to current month)"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    Get monthly top winners ranked by net PNL.
    
    Returns all accounts sorted by total net_pnl for the specified month.
    Includes account name from MT5, current equity, and monthly deposit/withdrawal totals.
    
    **Response:**
    - rank: Position in ranking (1-based)
    - login: MT5 account login
    - account_name: Name from MT5 account
    - current_equity: Current equity from MT5
    - total_deposit: Sum of deposits for the month
    - total_withdrawal: Sum of withdrawals for the month
    - total_net_pnl: Sum of net_pnl for the month
    """
    from app.domain.models import MT5Account
    
    # Default to current year/month
    now = datetime.now()
    target_year = year if year else now.year
    target_month = month if month else now.month
    
    # Validate month
    if not 1 <= target_month <= 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")
    
    logger.info("get_monthly_top_winners", year=target_year, month=target_month)
    
    # Get aggregated data from repository (now includes deposits/withdrawals)
    repo = DailyPnLRepository(db)
    monthly_data = await repo.get_monthly_aggregated_detailed(target_year, target_month)
    
    # Get current equity from MT5 for each account
    mt5_service = MT5ManagerService()
    
    # Fetch account details and current equity
    results = []
    rank = 1
    for login, total_net_pnl, total_deposit, total_withdrawal in monthly_data:
        # Get current account info from MT5 (includes name and equity)
        account_name = "Unknown"
        current_equity = 0.0
        try:
            account_info = await mt5_service.get_account_info(login)
            if account_info:
                account_name = account_info.name if account_info.name else "Unknown"
                current_equity = account_info.equity
        except Exception as e:
            logger.warning("failed_to_get_account_info", login=login, error=str(e))
        
        results.append({
            "rank": rank,
            "login": login,
            "account_name": account_name,
            "current_equity": round(current_equity, 2),
            "total_deposit": round(total_deposit, 2),
            "total_withdrawal": round(total_withdrawal, 2),
            "total_net_pnl": round(total_net_pnl, 2),
        })
        rank += 1
    
    return {
        "year": target_year,
        "month": target_month,
        "count": len(results),
        "winners": results,
    }
