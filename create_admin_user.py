"""Create admin user for CRM system"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.db import AsyncSessionLocal
from app.repositories.users_repo import UsersRepository
from app.domain.enums import UserRole


async def create_admin():
    """Create admin user"""
    email = 'admin@crm.com'
    password = 'Admin123!'
    full_name = 'System Administrator'
    
    async with AsyncSessionLocal() as db:
        try:
            repo = UsersRepository(db)
            
            # Check if user already exists
            existing = await repo.get_by_email(email)
            if existing:
                print(f'❌ User with email {email} already exists')
                print(f'   User ID: {existing.id}')
                print(f'   Role: {existing.role}')
                return False
            
            # Create admin user
            user = await repo.create(
                email=email,
                password=password,
                role=UserRole.ADMIN,
                full_name=full_name
            )
            await db.commit()
            
            print('✅ Admin user created successfully!')
            print(f'   Email: {user.email}')
            print(f'   Role: {user.role}')
            print(f'   Name: {user.full_name}')
            print(f'   Password: {password}')
            print('\n⚠️  IMPORTANT: Change the password after first login!')
            return True
            
        except Exception as e:
            print(f'❌ Failed to create admin user: {e}')
            import traceback
            traceback.print_exc()
            return False


if __name__ == '__main__':
    success = asyncio.run(create_admin())
    sys.exit(0 if success else 1)
