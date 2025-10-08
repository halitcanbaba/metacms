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


# Customer DTOs
class CustomerBase(BaseDTO):
    """Base customer DTO."""

    name: str
    email: EmailStr | None = None
    phone: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class CustomerCreate(CustomerBase):
    """Customer creation DTO."""

    pass


class CustomerUpdate(BaseModel):
    """Customer update DTO."""

    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class CustomerResponse(CustomerBase):
    """Customer response DTO."""

    id: int
    external_ids: dict[str, Any] | None = None
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

    customer_id: int
    password: str = Field(..., min_length=8)


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
