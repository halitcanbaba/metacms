"""Application enumerations."""
from enum import Enum


class UserRole(str, Enum):
    """User role enumeration."""

    ADMIN = "admin"
    DEALER = "dealer"
    SUPPORT = "support"
    VIEWER = "viewer"


class BalanceOperationType(str, Enum):
    """Balance operation type enumeration."""

    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    CREDIT_IN = "credit_in"
    CREDIT_OUT = "credit_out"


class BalanceOperationStatus(str, Enum):
    """Balance operation status enumeration."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


class MT5AccountStatus(str, Enum):
    """MT5 account status enumeration."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class AuditAction(str, Enum):
    """Audit action types."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    BALANCE_OPERATION = "balance_operation"
    PASSWORD_RESET = "password_reset"
    GROUP_MOVE = "group_move"


class PipedriveEventType(str, Enum):
    """Pipedrive webhook event types."""

    ORGANIZATION_ADDED = "added.organization"
    ORGANIZATION_UPDATED = "updated.organization"
    ORGANIZATION_DELETED = "deleted.organization"
    PERSON_ADDED = "added.person"
    PERSON_UPDATED = "updated.person"
    PERSON_DELETED = "deleted.person"
    DEAL_ADDED = "added.deal"
    DEAL_UPDATED = "updated.deal"
    DEAL_DELETED = "deleted.deal"
