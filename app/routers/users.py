"""
Users router for user management (CRUD operations).
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from app.db import get_db
from app.deps import get_current_user_id
from app.domain.models import User
from app.domain.enums import UserRole, AuditAction
from app.repositories.users_repo import UsersRepository
from app.repositories.audit_repo import AuditRepository
import structlog

logger = structlog.get_logger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Request/Response Models
class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: str = "viewer"
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

router = APIRouter(
    prefix="/api/users",
    tags=["Users"],
)


@router.get("")
async def get_users(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    Get all users with pagination and search.
    
    **Parameters:**
    - skip: Number of records to skip (default: 0)
    - limit: Maximum number of records to return (default: 100)
    - search: Search by email or full name
    
    **Returns:**
    - List of users with total count
    """
    repo = UsersRepository(db)
    
    # Build query
    query = select(User).where(User.id.isnot(None))
    
    # Add search filter
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (User.email.ilike(search_filter)) | 
            (User.full_name.ilike(search_filter))
        )
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    total = result.scalar_one()
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(User.id.desc())
    result = await db.execute(query)
    users = result.scalars().all()
    
    return {
        "total": total,
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
                "is_active": user.is_active,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
            for user in users
        ],
    }


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """Get user by ID."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    request: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    Create a new user.
    
    **Parameters:**
    - email: User email (unique)
    - password: User password (will be hashed)
    - full_name: User's full name (optional)
    - role: User role (admin/manager/viewer, default: viewer)
    - is_active: Whether user is active (default: true)
    """
    # Check if email already exists
    stmt = select(User).where(User.email == request.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Validate role
    try:
        user_role = UserRole(request.role.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")
    
    # Hash password
    password_hash = pwd_context.hash(request.password)
    
    # Create user
    user = User(
        email=request.email,
        password_hash=password_hash,
        full_name=request.full_name,
        role=user_role,
        is_active=request.is_active,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Create audit log
    audit_repo = AuditRepository(db)
    await audit_repo.create(
        actor_id=current_user_id,
        action=AuditAction.CREATE,
        entity="user",
        entity_id=str(user.id),
        after={
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_active": user.is_active,
        },
    )
    await db.commit()
    
    logger.info("user_created", user_id=user.id, email=request.email)
    
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    request: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    Update user information.
    
    **Parameters:**
    - email: New email (optional)
    - password: New password (optional, will be hashed)
    - full_name: New full name (optional)
    - role: New role (optional)
    - is_active: New active status (optional)
    """
    # Get user
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Store original state for audit log
    before_state = {
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
    }
    
    # Update fields
    if request.email is not None:
        # Check if new email is already taken
        stmt = select(User).where(User.email == request.email, User.id != user_id)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")
        user.email = request.email
    
    if request.password is not None:
        user.password_hash = pwd_context.hash(request.password)
    
    if request.full_name is not None:
        user.full_name = request.full_name
    
    if request.role is not None:
        try:
            user.role = UserRole(request.role.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")
    
    if request.is_active is not None:
        user.is_active = request.is_active
    
    await db.commit()
    await db.refresh(user)
    
    # Create audit log
    after_state = {
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
    }
    
    audit_repo = AuditRepository(db)
    await audit_repo.create(
        actor_id=current_user_id,
        action=AuditAction.UPDATE,
        entity="user",
        entity_id=str(user.id),
        before=before_state,
        after=after_state,
    )
    await db.commit()
    
    logger.info("user_updated", user_id=user.id, email=user.email)
    
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
):
    """Delete a user."""
    # Get user
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent deleting yourself
    if user.id == current_user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    # Store user data for audit log before deletion
    before_state = {
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "is_active": user.is_active,
    }
    
    # Create audit log before deletion
    audit_repo = AuditRepository(db)
    await audit_repo.create(
        actor_id=current_user_id,
        action=AuditAction.DELETE,
        entity="user",
        entity_id=str(user.id),
        before=before_state,
    )
    
    await db.delete(user)
    await db.commit()
    
    logger.info("user_deleted", user_id=user.id, email=user.email)
    
    return None
