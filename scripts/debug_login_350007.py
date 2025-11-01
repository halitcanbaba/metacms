"""Debug script to test daily PNL calculation for login 350007."""
import asyncio
import sys
from pathlib import Path
from datetime import date

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.mt5_manager import get_mt5_service
from app.services.daily_pnl import DailyPnLService


async def debug_login_350007():
    """Debug PNL calculation for login 350007."""
    print("=" * 80)
    print("Debugging PNL Calculation for Login 350007")
    print("=" * 80)
    
    mt5_service = get_mt5_service()
    pnl_service = DailyPnLService(mt5_service)
    
    try:
        await mt5_service.connect()
        print("✓ Connected to MT5\n")
        
        login = 350007
        target_date = date(2025, 10, 31)
        
        print(f"Target: Login {login}, Date {target_date}\n")
        
        # Step 1: Check daily reports
        print("Step 1: Fetching daily reports...")
        print("-" * 80)
        prev_date = date(2025, 10, 30)
        reports = await mt5_service.get_daily_reports(
            login=login,
            from_date=prev_date,
            to_date=target_date
        )
        
        print(f"Found {len(reports)} reports")
        for report in reports:
            print(f"\n  Date: {report.date}")
            print(f"  Login: {report.login}")
            print(f"  Balance: ${report.balance:,.2f}")
            print(f"  Present Equity: ${report.present_equity:,.2f}")
            print(f"  Equity Prev Day: ${report.equity_prev_day:,.2f}")
            print(f"  Floating Profit: ${report.floating_profit:,.2f}")
            print(f"  Daily Agent (total_ib): ${report.daily_agent:,.2f}")
        
        # Step 2: Check deal history
        print(f"\n\nStep 2: Fetching deal history for {target_date}...")
        print("-" * 80)
        deals = await mt5_service.get_deal_history(
            login=login,
            from_date=target_date,
            to_date=target_date
        )
        
        print(f"Found {len(deals)} deals")
        if deals:
            for deal in deals:
                print(f"\n  Deal #{deal.deal_id}")
                print(f"  Action: {deal.action}")
                print(f"  Amount: ${deal.amount:,.2f}")
                print(f"  Comment: {deal.comment}")
                print(f"  Tag: {deal.tag}")
        else:
            print("  No deals found")
        
        # Step 3: Calculate PNL
        print(f"\n\nStep 3: Calculating PNL...")
        print("-" * 80)
        pnl = await pnl_service.calculate_daily_pnl(target_date, login)
        
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
            print(f"  Rebate: ${pnl.rebate:,.2f}")
            print(f"\n  ► Equity PNL: ${pnl.equity_pnl:,.2f}")
            
            print(f"\n  Formula Check:")
            calculated = pnl.present_equity - pnl.equity_prev_day - pnl.net_deposit - pnl.net_credit_promotion - pnl.total_ib
            print(f"    {pnl.present_equity:.2f} - {pnl.equity_prev_day:.2f} - {pnl.net_deposit:.2f} - {pnl.net_credit_promotion:.2f} - {pnl.total_ib:.2f}")
            print(f"    = {calculated:.2f}")
            print(f"    Stored: {pnl.equity_pnl:.2f}")
            print(f"    Match: {'✓' if abs(calculated - pnl.equity_pnl) < 0.01 else '✗'}")
        else:
            print("\n✗ No PNL data calculated")
        
        # Step 4: Test all logins calculation
        print(f"\n\nStep 4: Testing all logins calculation for {target_date}...")
        print("-" * 80)
        all_pnl = await pnl_service.calculate_all_logins_pnl(target_date)
        
        print(f"Calculated PNL for {len(all_pnl)} accounts")
        
        # Find our test account
        test_account = next((p for p in all_pnl if p.login == login), None)
        if test_account:
            print(f"\n  Found login {login} in all_logins result:")
            print(f"    Equity PNL: ${test_account.equity_pnl:,.2f}")
            print(f"    Match with single calculation: {'✓' if pnl and abs(test_account.equity_pnl - pnl.equity_pnl) < 0.01 else '✗'}")
        else:
            print(f"\n  ✗ Login {login} NOT found in all_logins result!")
        
        # Show institution aggregate
        institution = pnl_service.aggregate_institution_pnl(all_pnl, target_date)
        print(f"\n  Institution Aggregate (login=0):")
        print(f"    Total Accounts: {len(all_pnl)}")
        print(f"    Total Equity PNL: ${institution.equity_pnl:,.2f}")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await mt5_service.disconnect()
        print(f"\n{'=' * 80}")
        print("✓ Disconnected from MT5")


if __name__ == "__main__":
    asyncio.run(debug_login_350007())
