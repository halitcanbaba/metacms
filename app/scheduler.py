"""Scheduler for background jobs."""
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import structlog

from app.db import AsyncSessionLocal
from app.services.daily_pnl import DailyPnLService
from app.repositories.daily_pnl_repo import DailyPnLRepository

logger = structlog.get_logger()

scheduler = AsyncIOScheduler()


async def calculate_yesterday_pnl():
    """
    Job to calculate yesterday's P&L for all accounts.
    Runs daily at 00:05 to calculate the previous day's metrics.
    """
    try:
        yesterday = (datetime.now() - timedelta(days=1)).date()
        logger.info("daily_pnl_job_started", date=yesterday)
        
        # Calculate for all accounts
        service = DailyPnLService()
        all_pnl = await service.calculate_all_logins_pnl(yesterday)
        
        if not all_pnl:
            logger.warning("no_accounts_found_for_pnl", date=yesterday)
            return
        
        # Save to database
        async with AsyncSessionLocal() as db:
            repo = DailyPnLRepository(db)
            saved_count = 0
            
            # Save individual account records
            for pnl in all_pnl:
                try:
                    metrics_dict = {
                        "day": datetime.strptime(pnl.date, "%Y-%m-%d").date(),
                        "login": pnl.login,
                        "deposit": 0.0,
                        "withdrawal": 0.0,
                        "net_deposit": pnl.net_deposit,
                        "promotion": pnl.promotion,
                        "credit": 0.0,
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
                    logger.error("failed_to_save_account_pnl",
                               date=yesterday,
                               login=pnl.login,
                               error=str(e))
            
            # Save institution aggregate (login=0)
            institution_pnl = service.aggregate_institution_pnl(all_pnl, yesterday)
            try:
                institution_dict = {
                    "day": datetime.strptime(institution_pnl.date, "%Y-%m-%d").date(),
                    "login": 0,
                    "deposit": 0.0,
                    "withdrawal": 0.0,
                    "net_deposit": institution_pnl.net_deposit,
                    "promotion": institution_pnl.promotion,
                    "credit": 0.0,
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
            except Exception as e:
                logger.error("failed_to_save_institution_pnl",
                           date=yesterday,
                           error=str(e))
            
            await db.commit()
        
        logger.info("daily_pnl_job_completed",
                   date=yesterday,
                   total_accounts=len(all_pnl),
                   saved_count=saved_count,
                   institution_net_pnl=institution_pnl.net_pnl)
        
    except Exception as e:
        logger.error("daily_pnl_job_failed",
                    error=str(e),
                    error_type=type(e).__name__)


def start_scheduler():
    """Start the background job scheduler."""
    try:
        # Add job to run daily at 00:05 (5 minutes past midnight)
        scheduler.add_job(
            calculate_yesterday_pnl,
            trigger=CronTrigger(hour=0, minute=5),
            id="daily_pnl_job",
            name="Calculate Daily P&L",
            replace_existing=True,
            misfire_grace_time=3600,  # Allow 1 hour grace period
        )
        
        scheduler.start()
        logger.info("scheduler_started",
                   jobs=[job.id for job in scheduler.get_jobs()])
        
    except Exception as e:
        logger.error("scheduler_start_failed", error=str(e))


def stop_scheduler():
    """Stop the background job scheduler."""
    try:
        scheduler.shutdown()
        logger.info("scheduler_stopped")
    except Exception as e:
        logger.error("scheduler_stop_failed", error=str(e))
