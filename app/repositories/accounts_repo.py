"""MT5 Accounts repository for database operations."""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import MT5AccountStatus
from app.domain.models import MT5Account


class AccountsRepository:
    """Repository for MT5Account model operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, account_id: int) -> MT5Account | None:
        """Get account by ID."""
        result = await self.db.execute(select(MT5Account).where(MT5Account.id == account_id))
        return result.scalar_one_or_none()

    async def get_by_login(self, login: int) -> MT5Account | None:
        """Get account by MT5 login."""
        result = await self.db.execute(select(MT5Account).where(MT5Account.login == login))
        return result.scalar_one_or_none()

    async def get_by_customer(self, customer_id: int) -> list[MT5Account]:
        """Get all accounts for a customer."""
        result = await self.db.execute(
            select(MT5Account).where(MT5Account.customer_id == customer_id).order_by(MT5Account.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_all(self, skip: int = 0, limit: int = 20, status: MT5AccountStatus | None = None) -> tuple[list[MT5Account], int]:
        """
        List all accounts with pagination and optional status filter.
        
        Returns:
            Tuple of (accounts list, total count)
        """
        # Build query
        query = select(MT5Account)
        count_query = select(func.count()).select_from(MT5Account)

        if status:
            query = query.where(MT5Account.status == status)
            count_query = count_query.where(MT5Account.status == status)

        # Get total count
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        # Get accounts
        result = await self.db.execute(query.offset(skip).limit(limit).order_by(MT5Account.created_at.desc()))
        accounts = list(result.scalars().all())

        return accounts, total

    async def create(
        self,
        customer_id: int,
        login: int,
        group: str,
        leverage: int,
        currency: str,
        status: MT5AccountStatus = MT5AccountStatus.ACTIVE,
        balance: float = 0.0,
        credit: float = 0.0,
        external_ids: dict | None = None,
        metadata: dict | None = None,
    ) -> MT5Account:
        """Create a new MT5 account."""
        account = MT5Account(
            customer_id=customer_id,
            login=login,
            group=group,
            leverage=leverage,
            currency=currency,
            status=status,
            balance=balance,
            credit=credit,
            external_ids=external_ids or {},
            metadata=metadata or {},
        )

        self.db.add(account)
        await self.db.flush()
        await self.db.refresh(account)

        return account

    async def update(self, account: MT5Account) -> MT5Account:
        """Update an existing account."""
        self.db.add(account)
        await self.db.flush()
        await self.db.refresh(account)
        return account

    async def update_balance(self, login: int, balance: float, credit: float | None = None) -> MT5Account | None:
        """Update account balance (and optionally credit)."""
        account = await self.get_by_login(login)
        if account:
            account.balance = balance
            if credit is not None:
                account.credit = credit
            return await self.update(account)
        return None

    async def update_status(self, login: int, status: MT5AccountStatus) -> MT5Account | None:
        """Update account status."""
        account = await self.get_by_login(login)
        if account:
            account.status = status
            return await self.update(account)
        return None

    async def update_group(self, login: int, group: str) -> MT5Account | None:
        """Update account group."""
        account = await self.get_by_login(login)
        if account:
            account.group = group
            return await self.update(account)
        return None

    async def delete(self, account: MT5Account) -> None:
        """Delete an account."""
        await self.db.delete(account)
        await self.db.flush()

    async def get_total_balance_by_customer(self, customer_id: int) -> float:
        """Get total balance across all accounts for a customer."""
        result = await self.db.execute(
            select(func.sum(MT5Account.balance)).where(
                MT5Account.customer_id == customer_id, MT5Account.status == MT5AccountStatus.ACTIVE
            )
        )
        total = result.scalar_one_or_none()
        return total or 0.0

    async def count_by_status(self, status: MT5AccountStatus) -> int:
        """Count accounts by status."""
        result = await self.db.execute(select(func.count()).select_from(MT5Account).where(MT5Account.status == status))
        return result.scalar_one()
