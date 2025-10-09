"""Reset admin password."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from passlib.context import CryptContext

from app.domain.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def reset_password():
    """Reset admin password."""
    # SQLite connection
    database_url = "sqlite+aiosqlite:///./dev.db"
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # New password
    new_password = input("Enter new admin password (default: admin123): ").strip() or "admin123"
    
    async with async_session() as session:
        # Get admin user
        result = await session.execute(
            select(User).where(User.email == "admin@example.com")
        )
        admin = result.scalar_one_or_none()
        
        if not admin:
            print("❌ Admin user not found!")
            print("\nCreating admin user...")
            
            from app.domain.enums import UserRole
            admin = User(
                email="admin@example.com",
                password_hash=pwd_context.hash(new_password),
                role=UserRole.ADMIN,
                is_active=True,
                full_name="System Administrator"
            )
            session.add(admin)
            await session.commit()
            await session.refresh(admin)
            
            print("✅ Admin user created!")
        else:
            # Update password
            admin.password_hash = pwd_context.hash(new_password)
            await session.commit()
            print("✅ Password updated!")
        
        print(f"\n{'='*50}")
        print(f"📧 Email: {admin.email}")
        print(f"🔑 Password: {new_password}")
        print(f"👤 Role: {admin.role}")
        print(f"✅ Active: {admin.is_active}")
        print(f"{'='*50}\n")

if __name__ == "__main__":
    asyncio.run(reset_password())
