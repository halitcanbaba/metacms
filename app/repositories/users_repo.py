"""Users repository for database operations."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import User
from app.security import hash_password


class UsersRepository:
    """Repository for User model operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, email: str, password: str, role: str, full_name: str | None = None) -> User:
        """Create a new user."""
        user = User(email=email, password_hash=hash_password(password), role=role, full_name=full_name, is_active=True)

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def update(self, user: User) -> User:
        """Update an existing user."""
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        """Delete a user."""
        await self.db.delete(user)
        await self.db.flush()

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        """List all users with pagination."""
        result = await self.db.execute(select(User).offset(skip).limit(limit))
        return list(result.scalars().all())
