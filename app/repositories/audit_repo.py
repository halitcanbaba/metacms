"""Audit logs repository for database operations."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import AuditAction
from app.domain.models import AuditLog


class AuditRepository:
    """Repository for AuditLog model operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, log_id: int) -> AuditLog | None:
        """Get audit log by ID."""
        result = await self.db.execute(select(AuditLog).where(AuditLog.id == log_id))
        return result.scalar_one_or_none()

    async def get_by_request_id(self, request_id: str) -> list[AuditLog]:
        """Get all audit logs for a request ID."""
        result = await self.db.execute(
            select(AuditLog).where(AuditLog.request_id == request_id).order_by(AuditLog.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_by_entity(
        self, entity: str, entity_id: str, skip: int = 0, limit: int = 20
    ) -> tuple[list[AuditLog], int]:
        """
        Get audit logs for a specific entity.
        
        Returns:
            Tuple of (logs list, total count)
        """
        # Get total count
        count_result = await self.db.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.entity == entity, AuditLog.entity_id == entity_id)
        )
        total = count_result.scalar_one()

        # Get logs
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.entity == entity, AuditLog.entity_id == entity_id)
            .offset(skip)
            .limit(limit)
            .order_by(AuditLog.created_at.desc())
        )
        logs = list(result.scalars().all())

        return logs, total

    async def get_by_actor(self, actor_id: int, skip: int = 0, limit: int = 20) -> tuple[list[AuditLog], int]:
        """
        Get audit logs by actor (user).
        
        Returns:
            Tuple of (logs list, total count)
        """
        # Get total count
        count_result = await self.db.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.actor_id == actor_id)
        )
        total = count_result.scalar_one()

        # Get logs
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.actor_id == actor_id)
            .offset(skip)
            .limit(limit)
            .order_by(AuditLog.created_at.desc())
        )
        logs = list(result.scalars().all())

        return logs, total

    async def list_all(
        self, skip: int = 0, limit: int = 20, action: AuditAction | None = None, entity: str | None = None
    ) -> tuple[list[AuditLog], int]:
        """
        List all audit logs with pagination and optional filters.
        
        Returns:
            Tuple of (logs list, total count)
        """
        # Build query
        query = select(AuditLog)
        count_query = select(func.count()).select_from(AuditLog)

        filters = []
        if action:
            filters.append(AuditLog.action == action)
        if entity:
            filters.append(AuditLog.entity == entity)

        if filters:
            query = query.where(*filters)
            count_query = count_query.where(*filters)

        # Get total count
        count_result = await self.db.execute(count_query)
        total = count_result.scalar_one()

        # Get logs
        result = await self.db.execute(query.offset(skip).limit(limit).order_by(AuditLog.created_at.desc()))
        logs = list(result.scalars().all())

        return logs, total

    async def get_recent(self, hours: int = 24, limit: int = 100) -> list[AuditLog]:
        """Get recent audit logs."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.created_at >= cutoff)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create(
        self,
        actor_id: int,
        action: AuditAction,
        entity: str,
        entity_id: str,
        before: dict | None = None,
        after: dict | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Create a new audit log entry."""
        log = AuditLog(
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            before=before,
            after=after,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)

        return log

    async def count_by_action(self, action: AuditAction) -> int:
        """Count logs by action type."""
        result = await self.db.execute(select(func.count()).select_from(AuditLog).where(AuditLog.action == action))
        return result.scalar_one()

    async def search(self, search_term: str, skip: int = 0, limit: int = 20) -> tuple[list[AuditLog], int]:
        """
        Search audit logs by entity or entity_id.
        
        Returns:
            Tuple of (logs list, total count)
        """
        search_filter = (AuditLog.entity.ilike(f"%{search_term}%")) | (AuditLog.entity_id.ilike(f"%{search_term}%"))

        # Get total count
        count_result = await self.db.execute(select(func.count()).select_from(AuditLog).where(search_filter))
        total = count_result.scalar_one()

        # Get logs
        result = await self.db.execute(
            select(AuditLog).where(search_filter).offset(skip).limit(limit).order_by(AuditLog.created_at.desc())
        )
        logs = list(result.scalars().all())

        return logs, total
