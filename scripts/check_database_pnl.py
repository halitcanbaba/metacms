"""Check database for daily PNL records."""
import asyncio
import sys
from pathlib import Path
from datetime import date

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.domain.models import DailyPnL


async def check_database():
    """Check database for daily PNL records."""
    print("=" * 80)
    print("Checking Database for Daily PNL Records")
    print("=" * 80)
    
    # Create database connection
    database_url = "sqlite+aiosqlite:///./dev.db"  # Root level, same as API
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Query for Oct 31 records
        target_date = date(2025, 10, 31)
        
        print(f"\nQuerying records for {target_date}...")
        print("-" * 80)
        
        stmt = select(DailyPnL).where(DailyPnL.day == target_date).order_by(DailyPnL.login)
        result = await session.execute(stmt)
        records = result.scalars().all()
        
        print(f"Found {len(records)} records\n")
        
        if records:
            # Show all records
            for record in records:
                login_display = "INSTITUTION" if record.login == 0 else record.login
                print(f"Login: {login_display:>12}")
                print(f"  Day: {record.day}")
                print(f"  Equity PNL: ${record.equity_pnl:,.2f}")
                print(f"  Net Deposit: ${record.net_deposit:,.2f}")
                print(f"  Net Credit/Promotion: ${record.net_credit_promotion:,.2f}")
                print(f"  Total IB: ${record.total_ib:,.2f}")
                print(f"  IB Rebate: ${record.ib_rebate:,.2f}")
                print(f"  Net PNL: ${record.net_pnl:,.2f}")
                print()
            
            # Statistics
            print("-" * 80)
            print("Statistics:")
            print(f"  Total Records: {len(records)}")
            
            individual_accounts = [r for r in records if r.login and r.login > 0]
            institution_record = next((r for r in records if r.login == 0), None)
            
            print(f"  Individual Accounts: {len(individual_accounts)}")
            if institution_record:
                print(f"  Institution Record: Yes (login=0)")
                print(f"    Institution Total PNL: ${institution_record.equity_pnl:,.2f}")
            
            # Verify sum
            if individual_accounts:
                individual_sum = sum(r.equity_pnl for r in individual_accounts)
                print(f"\n  Sum of Individual Equity PNLs: ${individual_sum:,.2f}")
                if institution_record:
                    print(f"  Institution Equity PNL: ${institution_record.equity_pnl:,.2f}")
                    match = abs(individual_sum - institution_record.equity_pnl) < 0.01
                    print(f"  Match: {'✓ YES' if match else '✗ NO'}")
        else:
            print("No records found")
    
    await engine.dispose()
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(check_database())
