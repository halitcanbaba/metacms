"""Balance operations repository for database operations."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import BalanceOperationStatus, BalanceOperationType
from app.domain.models import BalanceOperation


class BalanceRepository:
    """Repository for BalanceOperation model operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, operation_id: int) -> BalanceOperation | None:
        """Get balance operation by ID."""
        result = await self.db.execute(select(BalanceOperation).where(BalanceOperation.id == operation_id))
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, idempotency_key: str) -> BalanceOperation | None:
        """Get balance operation by idempotency key."""
        result = await self.db.execute(
            select(BalanceOperation).where(BalanceOperation.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    async def get_by_account(
        self, account_id: int, skip: int = 0, limit: int = 20
    ) -> tuple[list[BalanceOperation], int]:
        """
        Get balance operations for an account.
        
        Returns:
            Tuple of (operations list, total count)
        """
        # Get total count
        count_result = await self.db.execute(
            select(func.count()).select_from(BalanceOperation).where(BalanceOperation.account_id == account_id)
        )
        total = count_result.scalar_one()

        # Get operations
        result = await self.db.execute(
            select(BalanceOperation)
            .where(BalanceOperation.account_id == account_id)
            .offset(skip)
            .limit(limit)
            .order_by(BalanceOperation.created_at.desc())
        )
        operations = list(result.scalars().all())

        return operations, total

    async def get_by_login(self, login: int, skip: int = 0, limit: int = 20) -> tuple[list[BalanceOperation], int]:
        """
        Get balance operations for a login.
        
        Returns:
            Tuple of (operations list, total count)
        """
        # Get total count
        count_result = await self.db.execute(
            select(func.count()).select_from(BalanceOperation).where(BalanceOperation.login == login)
        )
        total = count_result.scalar_one()

        # Get operations
        result = await self.db.execute(
            select(BalanceOperation)
            .where(BalanceOperation.login == login)
            .offset(skip)
            .limit(limit)
            .order_by(BalanceOperation.created_at.desc())
        )
        operations = list(result.scalars().all())

        return operations, total

    async def list_all(
        self,
        skip: int = 0,
        limit: int = 20,
        status: BalanceOperationStatus | None = None,
        operation_type: BalanceOperationType | None = None,
        login: int | None = None,
    ) -> tuple[list[BalanceOperation], int]:
        """
        List all balance operations with pagination and optional filters.
        
        Returns:
            Tuple of (operations list, total count)
        """
        # Build query
        query = select(BalanceOperation)
        count_query = select(func.count()).select_from(BalanceOperation)

        if status:
            query = query.where(BalanceOperation.status == status)
            count_query = count_query.where(BalanceOperation.status == status)

        if operation_type:
            query = query.where(BalanceOperation.type == operation_type)
            count_query = count_query.where(BalanceOperation.type == operation_type)

        if login:
            query = query.where(BalanceOperation.login == login)
            count_query = count_query.where(BalanceOperation.login == login)

        # Get total count
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        # Get operations
        result = await self.db.execute(query.offset(skip).limit(limit).order_by(BalanceOperation.created_at.desc()))
        operations = list(result.scalars().all())

        return operations, total

    async def get_recent(self, hours: int = 24, limit: int = 50) -> list[BalanceOperation]:
        """Get recent balance operations."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await self.db.execute(
            select(BalanceOperation)
            .where(BalanceOperation.created_at >= cutoff)
            .order_by(BalanceOperation.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create(
        self,
        account_id: int,
        login: int,
        operation_type: BalanceOperationType,
        amount: float,
        requested_by: int,
        comment: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict | None = None,
    ) -> BalanceOperation:
        """Create a new balance operation."""
        operation = BalanceOperation(
            account_id=account_id,
            login=login,
            type=operation_type,
            amount=amount,
            comment=comment,
            requested_by=requested_by,
            status=BalanceOperationStatus.PENDING,
            idempotency_key=idempotency_key,
            metadata=metadata or {},
        )

        self.db.add(operation)
        await self.db.flush()
        await self.db.refresh(operation)

        return operation

    async def update(self, operation: BalanceOperation) -> BalanceOperation:
        """Update an existing balance operation."""
        self.db.add(operation)
        await self.db.flush()
        await self.db.refresh(operation)
        return operation

    async def approve(self, operation_id: int, approved_by: int) -> BalanceOperation | None:
        """Approve a balance operation."""
        operation = await self.get_by_id(operation_id)
        if operation and operation.status == BalanceOperationStatus.PENDING:
            operation.status = BalanceOperationStatus.APPROVED
            operation.approved_by = approved_by
            return await self.update(operation)
        return None

    async def complete(self, operation_id: int) -> BalanceOperation | None:
        """Mark a balance operation as completed."""
        operation = await self.get_by_id(operation_id)
        if operation and operation.status in [BalanceOperationStatus.PENDING, BalanceOperationStatus.APPROVED]:
            operation.status = BalanceOperationStatus.COMPLETED
            return await self.update(operation)
        return None

    async def fail(self, operation_id: int, error_message: str) -> BalanceOperation | None:
        """Mark a balance operation as failed."""
        operation = await self.get_by_id(operation_id)
        if operation:
            operation.status = BalanceOperationStatus.FAILED
            operation.error_message = error_message
            return await self.update(operation)
        return None

    async def reject(self, operation_id: int, approved_by: int, reason: str) -> BalanceOperation | None:
        """Reject a balance operation."""
        operation = await self.get_by_id(operation_id)
        if operation and operation.status == BalanceOperationStatus.PENDING:
            operation.status = BalanceOperationStatus.REJECTED
            operation.approved_by = approved_by
            operation.error_message = reason
            return await self.update(operation)
        return None

    async def get_total_by_type(
        self, operation_type: BalanceOperationType, status: BalanceOperationStatus | None = None
    ) -> float:
        """Get total amount by operation type and optional status."""
        query = select(func.sum(BalanceOperation.amount)).where(BalanceOperation.type == operation_type)

        if status:
            query = query.where(BalanceOperation.status == status)

        result = await self.db.execute(query)
        total = result.scalar_one_or_none()
        return total or 0.0

    async def count_by_status(self, status: BalanceOperationStatus) -> int:
        """Count operations by status."""
        result = await self.db.execute(
            select(func.count()).select_from(BalanceOperation).where(BalanceOperation.status == status)
        )
        return result.scalar_one()
