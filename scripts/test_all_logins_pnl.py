"""Test script for all logins PNL calculation."""
import asyncio
import sys
from pathlib import Path
from datetime import date

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.mt5_manager import get_mt5_service
from app.services.daily_pnl import DailyPnLService


async def test_all_logins_pnl():
    """Test PNL calculation for all accounts."""
    print("=" * 80)
    print("Testing All Logins PNL Calculation")
    print("=" * 80)
    
    mt5_service = get_mt5_service()
    pnl_service = DailyPnLService(mt5_service)
    
    try:
        await mt5_service.connect()
        print("✓ Connected to MT5")
        
        # Test parameters
        test_date = date(2025, 10, 31)  # October 31, 2025
        
        print(f"\nTest Date: {test_date}")
        
        # Calculate PNL for all accounts
        print(f"\n{'=' * 80}")
        print(f"Calculating PNL for ALL accounts on {test_date}...")
        print(f"{'=' * 80}")
        
        all_pnl = await pnl_service.calculate_all_logins_pnl(test_date)
        
        if all_pnl:
            print(f"\n✓ Calculated PNL for {len(all_pnl)} accounts")
            
            # Show sample accounts
            print(f"\nSample Individual Account PNLs:")
            for i, pnl in enumerate(all_pnl[:5]):  # First 5 accounts
                print(f"\n  Account #{i+1}:")
                print(f"    Login: {pnl.login}")
                print(f"    Group: {pnl.group}")
                print(f"    Present Equity: ${pnl.present_equity:,.2f}")
                print(f"    Equity Prev Day: ${pnl.equity_prev_day:,.2f}")
                print(f"    Net Deposit: ${pnl.net_deposit:,.2f}")
                print(f"    Total IB: ${pnl.total_ib:,.2f}")
                print(f"    Rebate: ${pnl.rebate:,.2f}")
                print(f"    ► Equity PNL: ${pnl.equity_pnl:,.2f}")
            
            if len(all_pnl) > 5:
                print(f"\n  ... and {len(all_pnl) - 5} more accounts")
            
            # Calculate institution aggregate
            print(f"\n{'=' * 80}")
            print(f"Calculating Institution Aggregate...")
            print(f"{'=' * 80}")
            
            institution_pnl = pnl_service.aggregate_institution_pnl(all_pnl, test_date)
            
            print(f"\n✓ Institution Total (login=0):")
            print(f"    Total Accounts: {len(all_pnl)}")
            print(f"    Total Present Equity: ${institution_pnl.present_equity:,.2f}")
            print(f"    Total Equity Prev Day: ${institution_pnl.equity_prev_day:,.2f}")
            print(f"    Total Net Deposit: ${institution_pnl.net_deposit:,.2f}")
            print(f"    Total Net Credit/Promotion: ${institution_pnl.net_credit_promotion:,.2f}")
            print(f"    Total IB: ${institution_pnl.total_ib:,.2f}")
            print(f"    Total Rebate: ${institution_pnl.rebate:,.2f}")
            print(f"    ► Total Equity PNL: ${institution_pnl.equity_pnl:,.2f}")
            
            # Verification
            individual_sum = sum(pnl.equity_pnl for pnl in all_pnl)
            print(f"\n  Verification:")
            print(f"    Sum of Individual PNLs: ${individual_sum:,.2f}")
            print(f"    Institution Aggregate: ${institution_pnl.equity_pnl:,.2f}")
            print(f"    Match: {'✓ YES' if abs(individual_sum - institution_pnl.equity_pnl) < 0.01 else '✗ NO'}")
            
            # Summary statistics
            print(f"\n{'=' * 80}")
            print(f"Summary Statistics")
            print(f"{'=' * 80}")
            
            positive_pnl = [p for p in all_pnl if p.equity_pnl > 0]
            negative_pnl = [p for p in all_pnl if p.equity_pnl < 0]
            zero_pnl = [p for p in all_pnl if p.equity_pnl == 0]
            
            print(f"\n  Accounts with Positive PNL: {len(positive_pnl)} ({len(positive_pnl)/len(all_pnl)*100:.1f}%)")
            print(f"  Accounts with Negative PNL: {len(negative_pnl)} ({len(negative_pnl)/len(all_pnl)*100:.1f}%)")
            print(f"  Accounts with Zero PNL: {len(zero_pnl)} ({len(zero_pnl)/len(all_pnl)*100:.1f}%)")
            
            if positive_pnl:
                max_profit = max(positive_pnl, key=lambda p: p.equity_pnl)
                print(f"\n  Highest Profit: Login {max_profit.login} = ${max_profit.equity_pnl:,.2f}")
            
            if negative_pnl:
                max_loss = min(negative_pnl, key=lambda p: p.equity_pnl)
                print(f"  Highest Loss: Login {max_loss.login} = ${max_loss.equity_pnl:,.2f}")
            
        else:
            print(f"\n✗ No PNL data available for {test_date}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await mt5_service.disconnect()
        print(f"\n✓ Disconnected from MT5")


if __name__ == "__main__":
    asyncio.run(test_all_logins_pnl())
