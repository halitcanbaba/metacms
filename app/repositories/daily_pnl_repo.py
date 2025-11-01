"""Repository for daily P&L data access."""
from datetime import date, datetime
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import DailyPnL
import structlog

logger = structlog.get_logger()


class DailyPnLRepository:
    """Repository for managing daily P&L records."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_or_update(self, metrics: dict) -> DailyPnL:
        """
        Create or update a daily P&L record.
        
        Args:
            metrics: Dict with all P&L metrics
            
        Returns:
            DailyPnL model instance
        """
        target_day = metrics["day"]
        login = metrics.get("login")
        
        # Convert date to datetime for SQLAlchemy
        if isinstance(target_day, date) and not isinstance(target_day, datetime):
            target_day = datetime.combine(target_day, datetime.min.time())
        
        # Check if record exists
        stmt = select(DailyPnL).where(
            and_(
                DailyPnL.day == target_day,
                DailyPnL.login == login if login is not None else DailyPnL.login.is_(None)
            )
        )
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()
        
        if record:
            # Update existing record
            for key, value in metrics.items():
                if key not in ['day', 'login'] and hasattr(record, key):
                    setattr(record, key, value)
            logger.info("daily_pnl_updated", day=target_day, login=login)
        else:
            # Create new record
            record = DailyPnL(
                day=target_day,
                login=login,
                deposit=metrics.get("deposit", 0.0),
                withdrawal=metrics.get("withdrawal", 0.0),
                net_deposit=metrics.get("net_deposit", 0.0),
                promotion=metrics.get("promotion", 0.0),
                credit=metrics.get("credit", 0.0),
                net_credit_promotion=metrics.get("net_credit_promotion", 0.0),
                ib_commission=metrics.get("ib_commission", 0.0),
                ib_lot_return=metrics.get("ib_lot_return", 0.0),
                ib_rebate=metrics.get("ib_rebate", 0.0),
                total_ib=metrics.get("total_ib", 0.0),
                commission=metrics.get("commission", 0.0),
                swap=metrics.get("swap", 0.0),
                closed_pnl=metrics.get("closed_pnl", 0.0),
                equity_pnl=metrics.get("equity_pnl", 0.0),
                a_book_pnl=metrics.get("a_book_pnl", 0.0),
                net_pnl=metrics.get("net_pnl", 0.0),
            )
            self.db.add(record)
            logger.info("daily_pnl_created", day=target_day, login=login)
        
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def get_by_date(
        self,
        target_date: date,
        login: Optional[int] = None
    ) -> Optional[DailyPnL]:
        """Get daily P&L record for a specific date."""
        if isinstance(target_date, date) and not isinstance(target_date, datetime):
            target_date = datetime.combine(target_date, datetime.min.time())
        
        stmt = select(DailyPnL).where(
            and_(
                DailyPnL.day == target_date,
                DailyPnL.login == login if login is not None else DailyPnL.login.is_(None)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_date_range(
        self,
        from_date: date,
        to_date: date,
        login: Optional[int] = None
    ) -> list[DailyPnL]:
        """Get daily P&L records for a date range."""
        if isinstance(from_date, date) and not isinstance(from_date, datetime):
            from_date = datetime.combine(from_date, datetime.min.time())
        if isinstance(to_date, date) and not isinstance(to_date, datetime):
            to_date = datetime.combine(to_date, datetime.max.time())
        
        filters = [
            DailyPnL.day >= from_date,
            DailyPnL.day <= to_date
        ]
        
        if login is not None:
            filters.append(DailyPnL.login == login)
        else:
            filters.append(DailyPnL.login.is_(None))
        
        stmt = select(DailyPnL).where(and_(*filters)).order_by(DailyPnL.day.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_latest(
        self,
        limit: int = 30,
        login: Optional[int] = None
    ) -> list[DailyPnL]:
        """Get latest daily P&L records."""
        filters = []
        if login is not None:
            filters.append(DailyPnL.login == login)
        else:
            filters.append(DailyPnL.login.is_(None))
        
        stmt = select(DailyPnL).where(and_(*filters)).order_by(DailyPnL.day.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
