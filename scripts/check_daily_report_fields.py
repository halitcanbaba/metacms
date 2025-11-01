"""Script to check all available fields from MT5 Daily Reports."""
import MT5Manager
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.settings import settings

def main():
    manager = MT5Manager.ManagerAPI()
    
    # Connect to MT5 server
    print(f"Connecting to {settings.mt5_manager_host}:{settings.mt5_manager_port}...")
    result = manager.Connect(
        f"{settings.mt5_manager_host}:{settings.mt5_manager_port}",
        settings.mt5_manager_login,
        settings.mt5_manager_password,
        timeout=10000
    )
    
    if not result:
        error = MT5Manager.LastError()
        print(f"Failed to connect: {error}")
        return
    
    print("Connected successfully!")
    
    # Get yesterday and today timestamps
    yesterday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    today = datetime.now()
    
    from_timestamp = int(yesterday.timestamp())
    to_timestamp = int(today.timestamp())
    
    print(f"\nFetching daily reports from {yesterday} to {today}...")
    print(f"Timestamps: {from_timestamp} to {to_timestamp}")
    
    # Try DailyRequestLightByGroup with wildcard
    reports = manager.DailyRequestLightByGroup("*", from_timestamp, to_timestamp)
    
    if reports is False:
        error = MT5Manager.LastError()
        print(f"Failed to get reports: {error}")
        manager.Disconnect()
        return
    
    if not reports:
        print("No reports found")
        manager.Disconnect()
        return
    
    print(f"\nReceived {len(reports)} reports")
    
    if len(reports) > 0:
        report = reports[0]
        print(f"\n{'='*80}")
        print("FIRST REPORT - ALL AVAILABLE FIELDS:")
        print(f"{'='*80}")
        
        # Get all attributes
        all_attrs = [attr for attr in dir(report) if not attr.startswith('_')]
        
        for attr in sorted(all_attrs):
            try:
                value = getattr(report, attr)
                print(f"{attr:30s} = {value}")
            except Exception as e:
                print(f"{attr:30s} = <ERROR: {e}>")
    
    manager.Disconnect()
    print("\nDisconnected")

if __name__ == "__main__":
    main()
