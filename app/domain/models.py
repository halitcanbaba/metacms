"""SQLAlchemy database models."""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.domain.enums import (
    AuditAction,
    BalanceOperationStatus,
    BalanceOperationType,
    MT5AccountStatus,
    UserRole,
)


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(Base, TimestampMixin):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.VIEWER, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="actor_user", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class Agent(Base, TimestampMixin):
    """Agent model for sales/support agents."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    meta_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    customers: Mapped[list["Customer"]] = relationship(
        "Customer", back_populates="agent", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Agent(id={self.id}, name={self.name}, email={self.email})>"


class Customer(Base, TimestampMixin):
    """Customer model."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    agent_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("agents.id"), nullable=True, index=True)
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    external_ids: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    meta_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    agent: Mapped["Agent | None"] = relationship("Agent", back_populates="customers", lazy="selectin")
    mt5_accounts: Mapped[list["MT5Account"]] = relationship(
        "MT5Account", back_populates="customer", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, name={self.name}, email={self.email})>"


class MT5Account(Base, TimestampMixin):
    """MT5 trading account model."""

    __tablename__ = "mt5_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    login: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    group: Mapped[str] = mapped_column(String(100), nullable=False)
    leverage: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    status: Mapped[MT5AccountStatus] = mapped_column(
        Enum(MT5AccountStatus), default=MT5AccountStatus.ACTIVE, nullable=False
    )
    balance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    credit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    external_ids: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    meta_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="mt5_accounts", lazy="selectin")
    balance_operations: Mapped[list["BalanceOperation"]] = relationship(
        "BalanceOperation", back_populates="account", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<MT5Account(id={self.id}, login={self.login}, group={self.group}, status={self.status})>"


class BalanceOperation(Base, TimestampMixin):
    """Balance operation model."""

    __tablename__ = "balance_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("mt5_accounts.id"), nullable=False, index=True)
    login: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    type: Mapped[BalanceOperationType] = mapped_column(Enum(BalanceOperationType), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    status: Mapped[BalanceOperationStatus] = mapped_column(
        Enum(BalanceOperationStatus), default=BalanceOperationStatus.PENDING, nullable=False
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    account: Mapped["MT5Account"] = relationship("MT5Account", back_populates="balance_operations", lazy="selectin")
    requester: Mapped["User"] = relationship("User", foreign_keys=[requested_by], lazy="selectin")
    approver: Mapped["User | None"] = relationship("User", foreign_keys=[approved_by], lazy="selectin")

    def __repr__(self) -> str:
        return f"<BalanceOperation(id={self.id}, login={self.login}, type={self.type}, amount={self.amount}, status={self.status})>"


class AuditLog(Base):
    """Audit log model for tracking all changes."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False, index=True)
    entity: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    actor_user: Mapped["User"] = relationship("User", back_populates="audit_logs", lazy="selectin")

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, entity={self.entity}, entity_id={self.entity_id})>"


class PipedriveToken(Base, TimestampMixin):
    """Pipedrive OAuth token storage."""

    __tablename__ = "pipedrive_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_type: Mapped[str] = mapped_column(String(50), default="Bearer", nullable=False)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<PipedriveToken(id={self.id}, expires_at={self.expires_at}, is_active={self.is_active})>"


class DailyPnL(Base, TimestampMixin):
    """Daily P&L tracking model."""

    __tablename__ = "daily_pnl"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    day: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, index=True)
    login: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True, comment="MT5 login, NULL for system-wide")
    
    # Deposit/Withdrawal metrics
    deposit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="Tagged deposits (DT/WT)")
    withdrawal: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="Tagged withdrawals")
    net_deposit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="deposit - withdrawal")
    promotion: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="Non-tagged operations")
    
    # Credit metrics
    credit: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="Credit operations")
    net_credit_promotion: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="credit + promotion")
    
    # IB metrics
    ib_commission: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="IB commission paid")
    ib_lot_return: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="IB lot return")
    ib_rebate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="IB rebate")
    total_ib: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="Total IB costs")
    
    # Trading metrics
    commission: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="Trading commissions")
    swap: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="Swap/rollover")
    closed_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="Realized P&L")
    
    # Equity metrics
    equity_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="Equity change")
    a_book_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="A-book P&L")
    
    # Net P&L
    net_pnl: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="Total net P&L")

    def __repr__(self) -> str:
        return f"<DailyPnL(day={self.day}, login={self.login}, net_pnl={self.net_pnl})>"
