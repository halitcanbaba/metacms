"""Test script for daily PNL calculation with rebate tracking."""
import asyncio
import sys
from pathlib import Path
from datetime import date

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.mt5_manager import get_mt5_service
from app.services.daily_pnl import DailyPnLService


async def test_daily_pnl():
    """Test daily PNL calculation."""
    print("=" * 80)
    print("Testing Daily PNL Calculation with Rebate Tracking")
    print("=" * 80)
    
    mt5_service = get_mt5_service()
    pnl_service = DailyPnLService(mt5_service)
    
    try:
        await mt5_service.connect()
        print("✓ Connected to MT5")
        
        # Test parameters - adjust these as needed
        test_login = 350001  # Replace with a valid login
        test_date = date(2025, 10, 31)  # October 31, 2025
        
        print(f"\nTest Parameters:")
        print(f"  Login: {test_login}")
        print(f"  Target Date: {test_date}")
        
        # Calculate PNL
        print(f"\n{'=' * 80}")
        print(f"Calculating PNL for {test_date}...")
        print(f"{'=' * 80}")
        
        pnl = await pnl_service.calculate_daily_pnl(test_date, test_login)
        
        if pnl:
            print(f"\n✓ PNL Calculation Result:")
            print(f"  Login: {pnl.login}")
            print(f"  Date: {pnl.date}")
            print(f"  Group: {pnl.group}")
            print(f"  Currency: {pnl.currency}")
            print(f"\n  Present Equity: ${pnl.present_equity:,.2f}")
            print(f"  Equity Prev Day: ${pnl.equity_prev_day:,.2f}")
            print(f"  Net Deposit: ${pnl.net_deposit:,.2f}")
            print(f"  Net Credit/Promotion: ${pnl.net_credit_promotion:,.2f}")
            print(f"  Total IB: ${pnl.total_ib:,.2f}")
            print(f"  Rebate (REB tags): ${pnl.rebate:,.2f}")
            print(f"\n  ► Equity PNL: ${pnl.equity_pnl:,.2f}")
            
            print(f"\n  Formula Verification:")
            print(f"    {pnl.present_equity:,.2f} - {pnl.equity_prev_day:,.2f} - {pnl.net_deposit:,.2f} - {pnl.net_credit_promotion:,.2f} - {pnl.total_ib:,.2f}")
            print(f"    = {pnl.equity_pnl:,.2f}")
            
            # Test rebate detection
            print(f"\n{'=' * 80}")
            print(f"Testing REB Comment Detection...")
            print(f"{'=' * 80}")
            
            deals = await mt5_service.get_deal_history(
                login=test_login,
                from_date=test_date,
                to_date=test_date
            )
            
            rebate_deals = [d for d in deals if d.tag == "Rebate"]
            print(f"\n  Total deals on {test_date}: {len(deals)}")
            print(f"  REB-tagged deals: {len(rebate_deals)}")
            
            if rebate_deals:
                print(f"\n  Rebate Deals:")
                for deal in rebate_deals:
                    print(f"    Deal #{deal.deal_id}: {deal.comment} = ${deal.amount:,.2f}")
            
        else:
            print(f"\n✗ No PNL data available for login {test_login} on {test_date}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await mt5_service.disconnect()
        print(f"\n✓ Disconnected from MT5")


if __name__ == "__main__":
    asyncio.run(test_daily_pnl())
