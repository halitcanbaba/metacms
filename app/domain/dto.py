"""Data Transfer Objects (DTOs) for API requests and responses."""
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.enums import (
    AuditAction,
    BalanceOperationStatus,
    BalanceOperationType,
    MT5AccountStatus,
    UserRole,
)


# Base DTOs
class BaseDTO(BaseModel):
    """Base DTO with common configuration."""

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


# Authentication DTOs
class LoginRequest(BaseModel):
    """Login request DTO."""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response DTO."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Refresh token request DTO."""

    refresh_token: str


# User DTOs
class UserBase(BaseDTO):
    """Base user DTO."""

    email: EmailStr
    role: UserRole
    full_name: str | None = None


class UserCreate(UserBase):
    """User creation DTO."""

    password: str


class UserUpdate(BaseModel):
    """User update DTO."""

    email: EmailStr | None = None
    role: UserRole | None = None
    full_name: str | None = None
    is_active: bool | None = None


class UserResponse(UserBase):
    """User response DTO."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Agent DTOs
class AgentBase(BaseDTO):
    """Base agent DTO."""

    name: str
    email: EmailStr
    phone: str | None = None


class AgentCreate(AgentBase):
    """Agent creation DTO."""

    pass


class AgentUpdate(BaseModel):
    """Agent update DTO."""

    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    is_active: bool | None = None


class AgentResponse(AgentBase):
    """Agent response DTO."""

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Customer DTOs
class CustomerBase(BaseDTO):
    """Base customer DTO."""

    name: str
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    agent_id: int | None = None
    tags: list[str] | None = None
    meta_data: dict[str, Any] | None = None


class CustomerCreate(CustomerBase):
    """Customer creation DTO."""

    pass


class CustomerUpdate(BaseModel):
    """Customer update DTO."""

    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    agent_id: int | None = None
    tags: list[str] | None = None
    meta_data: dict[str, Any] | None = None


class CustomerResponse(CustomerBase):
    """Customer response DTO."""

    id: int
    external_ids: dict[str, Any] | None = None
    mt5_accounts: list["MT5AccountResponse"] = []
    created_at: datetime
    updated_at: datetime


# MT5 Account DTOs
class MT5AccountBase(BaseDTO):
    """Base MT5 account DTO."""

    group: str
    leverage: int = 100
    currency: str = "USD"


class MT5AccountCreate(MT5AccountBase):
    """MT5 account creation DTO."""

    # Either customer_id OR customer data fields
    customer_id: int | None = None
    
    # Customer data fields (used when auto-creating customer)
    customer_name: str | None = None
    customer_email: EmailStr | None = None
    customer_phone: str | None = None
    agent_id: int | None = None
    
    # MT5 account fields
    password: str = Field(..., min_length=8)
    name: str | None = None  # Full name to display on MT5 account


class MT5AccountUpdate(BaseModel):
    """MT5 account update DTO."""

    group: str | None = None
    leverage: int | None = None
    status: MT5AccountStatus | None = None


class MT5AccountResponse(MT5AccountBase):
    """MT5 account response DTO."""

    id: int
    customer_id: int
    login: int
    status: MT5AccountStatus
    balance: float
    credit: float
    external_ids: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class MT5AccountPasswordReset(BaseModel):
    """MT5 account password reset DTO."""

    new_password: str = Field(..., min_length=8)


class MT5AccountMoveGroup(BaseModel):
    """MT5 account move group DTO."""

    new_group: str


class MT5GroupResponse(BaseModel):
    """MT5 group response DTO."""

    name: str
    server: str | None = None
    currency: str | None = None
    company: str | None = None


class MT5DailyReportResponse(BaseModel):
    """MT5 daily report response DTO - Historical EOD snapshots with complete data."""

    login: int
    date: str  # YYYY-MM-DD format
    balance: float
    credit: float
    equity_prev_day: float  # Previous day equity - KEY FIELD!
    equity_prev_month: float  # Previous month equity
    balance_prev_day: float  # Previous day balance
    balance_prev_month: float  # Previous month balance
    margin: float
    margin_free: float
    margin_level: float
    margin_leverage: int
    floating_profit: float
    group: str
    currency: str
    currency_digits: int
    timestamp: int  # Unix timestamp of the report
    datetime_prev: int  # Previous day timestamp
    
    # Account info
    name: str
    email: str
    company: str
    
    # Agent commissions
    agent_daily: float
    agent_monthly: float
    commission_daily: float
    commission_monthly: float
    
    # Daily transactions breakdown
    daily_balance: float  # Balance operations (deposits/withdrawals)
    daily_credit: float  # Credit operations
    daily_charge: float  # Charges
    daily_correction: float  # Corrections
    daily_bonus: float  # Bonuses
    daily_comm_fee: float  # Commission fees
    daily_comm_instant: float  # Instant commissions
    daily_comm_round: float  # Round commissions
    daily_interest: float  # Interest
    daily_dividend: float  # Dividends
    daily_profit: float  # Closed profit
    daily_storage: float  # Storage/swap
    daily_agent: float  # Agent operations
    daily_so_compensation: float  # Stop-out compensation
    daily_so_compensation_credit: float  # Stop-out compensation credit
    daily_taxes: float  # Taxes
    
    # Interest rate
    interest_rate: float
    
    # Profit breakdown
    present_equity: float  # Current/present equity (floating profit)
    profit_storage: float  # Storage profit
    profit_assets: float  # Assets profit
    profit_liabilities: float  # Liabilities profit


class MT5DailyPnLResponse(BaseModel):
    """MT5 daily PNL calculation response DTO."""
    
    login: int
    date: str  # YYYY-MM-DD format
    present_equity: float  # Current day equity
    equity_prev_day: float  # Previous day equity
    net_deposit: float  # Net deposits for the day
    promotion: float  # Promotion amount for the day
    net_credit_promotion: float  # Net credit/promotions for the day
    total_ib: float  # Total IB commissions for the day
    rebate: float  # Total rebate for the day (from REB comments)
    equity_pnl: float  # Calculated: present_equity - equity_prev_day - net_deposit - net_credit_promotion - total_ib
    net_pnl: float  # Calculated: equity_pnl - promotion
    group: str
    currency: str


class MT5RealtimeEquityResponse(BaseModel):
    """MT5 realtime equity response DTO."""

    login: int
    name: str
    balance: float
    credit: float
    equity: float  # Balance + Credit + Floating Profit
    net_equity: float  # Equity - Credit (pure account value without credit)
    margin: float
    margin_free: float
    margin_level: float
    floating_profit: float
    group: str
    currency: str
    timestamp: int  # Unix timestamp when fetched


class MT5DealHistoryResponse(BaseModel):
    """MT5 deal history response DTO - Deposits, Withdrawals, Credits."""

    deal_id: int
    login: int
    action: str  # 'DEPOSIT', 'WITHDRAWAL', 'CREDIT', 'CREDIT_OUT', 'CHARGE', 'CORRECTION'
    amount: float
    balance_after: float
    comment: str
    timestamp: int
    datetime_str: str  # Human-readable datetime (YYYY-MM-DD HH:MM:SS)


# Balance Operation DTOs
class BalanceOperationBase(BaseDTO):
    """Base balance operation DTO."""

    type: BalanceOperationType
    amount: float = Field(..., gt=0)
    comment: str | None = None


class BalanceOperationCreate(BalanceOperationBase):
    """Balance operation creation DTO."""

    login: int


class BalanceOperationResponse(BalanceOperationBase):
    """Balance operation response DTO."""

    id: int
    account_id: int
    login: int
    status: BalanceOperationStatus
    requested_by: int
    approved_by: int | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class BalanceOperationApprove(BaseModel):
    """Balance operation approval DTO."""

    operation_id: int
    approved: bool
    rejection_reason: str | None = None


# Position DTOs
class OpenPosition(BaseDTO):
    """Open position DTO."""

    ticket: int
    login: int
    symbol: str
    volume: float
    type: str
    price_open: float
    price_current: float
    profit: float
    swap: float
    commission: float


class NetPosition(BaseDTO):
    """Net position by symbol DTO."""

    symbol: str
    buy_volume: float
    sell_volume: float
    net_volume: float
    net_profit: float
    positions_count: int


class PositionsSummary(BaseDTO):
    """Positions summary DTO."""

    total_positions: int
    total_volume: float
    total_profit: float
    net_positions: list[NetPosition]


# Audit DTOs
class AuditLogResponse(BaseDTO):
    """Audit log response DTO."""

    id: int
    actor_id: int
    action: AuditAction
    entity: str
    entity_id: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    request_id: str | None = None
    ip_address: str | None = None
    created_at: datetime
    
    # Actor user information
    actor_user: "UserResponse | None" = None


# Pipedrive DTOs
class PipedriveOrganization(BaseModel):
    """Pipedrive organization DTO."""

    name: str
    owner_id: int | None = None


class PipedrivePerson(BaseModel):
    """Pipedrive person DTO."""

    name: str
    email: list[EmailStr] | None = None
    phone: list[str] | None = None
    org_id: int | None = None


class PipedriveDeal(BaseModel):
    """Pipedrive deal DTO."""

    title: str
    value: float | None = None
    currency: str = "USD"
    org_id: int | None = None
    person_id: int | None = None


class PipedriveNote(BaseModel):
    """Pipedrive note DTO."""

    content: str
    org_id: int | None = None
    person_id: int | None = None
    deal_id: int | None = None


# Health DTOs
class HealthResponse(BaseModel):
    """Health check response DTO."""

    status: str
    timestamp: datetime
    database: str | None = None
    mt5: str | None = None
    pipedrive: str | None = None


# MT5 Password Reset DTOs
class MT5PasswordResetRequest(BaseModel):
    """MT5 password reset request DTO."""

    new_password: str = Field(..., min_length=8)
    password_type: str | None = Field(default="main", pattern="^(main|investor)$")


class MT5PasswordResetResponse(BaseModel):
    """MT5 password reset response DTO."""

    login: int
    success: bool
    message: str


class MT5GroupMoveRequest(BaseModel):
    """MT5 group move request DTO."""

    new_group: str = Field(..., min_length=1)


# Balance Operation Approval DTOs
class BalanceOperationApproval(BaseModel):
    """Balance operation approval/rejection DTO."""

    comment: str | None = None


# Pagination DTOs
class PaginationParams(BaseModel):
    """Pagination parameters DTO."""

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)


T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    items: list[T]
    total: int
    skip: int
    limit: int

    @property
    def pages(self) -> int:
        """Calculate total pages."""
        return (self.total + self.limit - 1) // self.limit if self.limit > 0 else 0

    @classmethod
    def create(cls, items: list[T], total: int, page: int, size: int) -> "PaginatedResponse[T]":
        """Create a paginated response."""
        skip = (page - 1) * size
        return cls(items=items, total=total, skip=skip, limit=size)


# Rebuild models to resolve forward references
CustomerResponse.model_rebuild()
