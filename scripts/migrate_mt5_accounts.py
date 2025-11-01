"""Migrate all MT5 accounts to the database."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.domain.models import MT5Account, Base
from app.services.mt5_manager import MT5ManagerService
from app.settings import settings
import structlog

logger = structlog.get_logger()

async def migrate_accounts():
    """Migrate all accounts from MT5 to database."""
    
    # Initialize async database connection
    # Convert sqlite:/// to sqlite+aiosqlite:///
    if settings.database_url.startswith("sqlite:///"):
        async_db_url = settings.database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    else:
        async_db_url = settings.database_url
    
    logger.info(f"Using database URL: {async_db_url}")
    engine = create_async_engine(async_db_url)
    
    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create async session
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with AsyncSessionLocal() as db:
    
        # Initialize MT5 service
        mt5_service = MT5ManagerService()
        
        try:
            # Connect to MT5
            await mt5_service.connect()
            logger.info("Connected to MT5 server")
            
            # Get all accounts from MT5
            def get_all_mt5_accounts():
                users = mt5_service.manager.UserGetByGroup("*")
                if users is False or users is None:
                    logger.error("Failed to get users from MT5")
                    return []
                return users
            
            users = await asyncio.get_event_loop().run_in_executor(None, get_all_mt5_accounts)
            logger.info(f"Found {len(users)} accounts in MT5")
            
            # Counters
            added = 0
            updated = 0
            skipped = 0
            
            # Process each user
            for user in users:
                try:
                    login = user.Login
                    
                    # Check if account exists in database (async query)
                    from sqlalchemy import select
                    result = await db.execute(select(MT5Account).filter(MT5Account.login == login))
                    existing = result.scalar_one_or_none()
                
                    # Determine status from rights
                    status = "active"
                    if hasattr(user, 'Rights'):
                        # Check if USER_RIGHT_ENABLED flag is set
                        if not (user.Rights & 1):  # USER_RIGHT_ENABLED = 1
                            status = "disabled"
                    
                    # Get full name from FirstName (we store full name there)
                    name = user.FirstName if hasattr(user, 'FirstName') else ""
                    
                    if existing:
                        # Update existing account
                        existing.group = user.Group if hasattr(user, 'Group') else existing.group
                        existing.leverage = user.Leverage if hasattr(user, 'Leverage') else existing.leverage
                        existing.balance = user.Balance if hasattr(user, 'Balance') else existing.balance
                        existing.credit = user.Credit if hasattr(user, 'Credit') else existing.credit
                        existing.status = status
                        existing.name = name
                        updated += 1
                        logger.debug(f"Updated account {login}")
                    else:
                        # Create new account
                        # Note: customer_id is set to 0 for now (no customer relationship)
                        new_account = MT5Account(
                            customer_id=0,  # Default, can be updated later
                            login=login,
                            group=user.Group if hasattr(user, 'Group') else "",
                            leverage=user.Leverage if hasattr(user, 'Leverage') else 100,
                            currency="USD",  # Default currency
                            status=status,
                            balance=user.Balance if hasattr(user, 'Balance') else 0.0,
                            credit=user.Credit if hasattr(user, 'Credit') else 0.0,
                            name=name
                        )
                        db.add(new_account)
                        added += 1
                        logger.debug(f"Added account {login}")
                        
                except Exception as e:
                    logger.error(f"Error processing account {user.Login if hasattr(user, 'Login') else 'unknown'}: {e}")
                    skipped += 1
                    continue
            
            # Commit all changes
            await db.commit()
            
            logger.info(f"Migration complete: Added={added}, Updated={updated}, Skipped={skipped}")
            print(f"\n✅ Migration Summary:")
            print(f"   Added: {added} new accounts")
            print(f"   Updated: {updated} existing accounts")
            print(f"   Skipped: {skipped} accounts (errors)")
            print(f"   Total processed: {len(users)}")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await db.rollback()
            raise
        finally:
            await mt5_service.disconnect()

if __name__ == "__main__":
    asyncio.run(migrate_accounts())
