"""FastAPI dependencies for dependency injection."""
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.security import decode_token, validate_token_type

# Security scheme for JWT bearer token
security = HTTPBearer()


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
) -> str:
    """Get the current user ID from JWT token."""
    token = credentials.credentials

    # Validate token type
    if not validate_token_type(token, "access"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user_id
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get the current user object from database."""
    from app.repositories.users_repo import UsersRepository

    repo = UsersRepository(db)
    user = await repo.get_by_id(int(user_id))

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(*allowed_roles: str):
    """Dependency factory for role-based authorization."""
    from app.domain.enums import UserRole

    async def role_checker(current_user=Depends(get_current_user)):
        # Admin has access to everything
        if current_user.role == UserRole.ADMIN.value:
            return current_user
        
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {', '.join(allowed_roles)}",
            )
        return current_user

    return role_checker


async def get_idempotency_key(
    idempotency_key: Annotated[str | None, Header()] = None,
) -> str | None:
    """Extract idempotency key from headers."""
    return idempotency_key


async def get_pipedrive_client():
    """Get Pipedrive client instance."""
    from app.services.pipedrive import PipedriveClient
    return PipedriveClient()


async def get_audit_service(db: AsyncSession = Depends(get_db)):
    """Get Audit service instance."""
    from app.services.audit import AuditService
    return AuditService(db)


async def get_mt5_manager():
    """Get MT5 Manager service instance."""
    from app.services.mt5_manager import MT5ManagerService
    return MT5ManagerService()


async def get_positions_service():
    """Get Positions service instance."""
    from app.services.positions import PositionsService
    return PositionsService()


# Commonly used dependencies
CurrentUser = Annotated[dict, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
IdempotencyKey = Annotated[str | None, Depends(get_idempotency_key)]
