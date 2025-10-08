"""Audit logging service for tracking all system changes."""
from typing import Any

import structlog
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import AuditAction
from app.repositories.audit_repo import AuditRepository

logger = structlog.get_logger()


class AuditService:
    """Service for creating and managing audit logs."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AuditRepository(db)

    async def log(
        self,
        actor_id: int,
        action: str | AuditAction,
        entity: str,
        entity_id: str | int,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        request: Request | None = None,
    ) -> None:
        """
        Create an audit log entry.
        
        Args:
            actor_id: ID of the user performing the action
            action: Type of action performed
            entity: Entity type (e.g., 'customer', 'account')
            entity_id: ID of the entity
            before: State before the action (for updates)
            after: State after the action
            request: Optional FastAPI request for extracting metadata
        """
        request_id = None
        ip_address = None
        user_agent = None

        if request:
            request_id = getattr(request.state, "request_id", None)
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

        try:
            await self.repo.create(
                actor_id=actor_id,
                action=action,
                entity=entity,
                entity_id=str(entity_id),
                before=before,
                after=after,
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            logger.info(
                "audit_log_created",
                actor_id=actor_id,
                action=action if isinstance(action, str) else action.value,
                entity=entity,
                entity_id=entity_id,
                request_id=request_id,
            )
        except Exception as e:
            # Don't fail the main operation if audit logging fails
            logger.error("audit_log_failed", error=str(e), actor_id=actor_id, action=action if isinstance(action, str) else action.value)

    async def log_customer_create(
        self, actor_id: int, customer_id: int, customer_data: dict, request: Request | None = None
    ) -> None:
        """Log customer creation."""
        await self.log(
            actor_id=actor_id,
            action=AuditAction.CREATE,
            entity="customer",
            entity_id=customer_id,
            after=customer_data,
            request=request,
        )

    async def log_customer_update(
        self,
        actor_id: int,
        customer_id: int,
        before_data: dict,
        after_data: dict,
        request: Request | None = None,
    ) -> None:
        """Log customer update."""
        await self.log(
            actor_id=actor_id,
            action=AuditAction.UPDATE,
            entity="customer",
            entity_id=customer_id,
            before=before_data,
            after=after_data,
            request=request,
        )

    async def log_account_create(
        self, actor_id: int, account_id: int, account_data: dict, request: Request | None = None
    ) -> None:
        """Log MT5 account creation."""
        await self.log(
            actor_id=actor_id,
            action=AuditAction.CREATE,
            entity="mt5_account",
            entity_id=account_id,
            after=account_data,
            request=request,
        )

    async def log_password_reset(
        self, actor_id: int, login: int, request: Request | None = None
    ) -> None:
        """Log password reset."""
        await self.log(
            actor_id=actor_id,
            action=AuditAction.PASSWORD_RESET,
            entity="mt5_account",
            entity_id=login,
            request=request,
        )

    async def log_group_move(
        self, actor_id: int, login: int, old_group: str, new_group: str, request: Request | None = None
    ) -> None:
        """Log account group move."""
        await self.log(
            actor_id=actor_id,
            action=AuditAction.GROUP_MOVE,
            entity="mt5_account",
            entity_id=login,
            before={"group": old_group},
            after={"group": new_group},
            request=request,
        )

    async def log_balance_operation(
        self, actor_id: int, operation_id: int, operation_data: dict, request: Request | None = None
    ) -> None:
        """Log balance operation."""
        await self.log(
            actor_id=actor_id,
            action=AuditAction.BALANCE_OPERATION,
            entity="balance_operation",
            entity_id=operation_id,
            after=operation_data,
            request=request,
        )

    async def log_login(self, user_id: int, request: Request | None = None) -> None:
        """Log user login."""
        await self.log(
            actor_id=user_id,
            action=AuditAction.LOGIN,
            entity="user",
            entity_id=user_id,
            request=request,
        )

    async def log_logout(self, user_id: int, request: Request | None = None) -> None:
        """Log user logout."""
        await self.log(
            actor_id=user_id,
            action=AuditAction.LOGOUT,
            entity="user",
            entity_id=user_id,
            request=request,
        )
