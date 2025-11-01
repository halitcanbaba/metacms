"""Create sample agents for testing."""
import sqlite3
from datetime import datetime

conn = sqlite3.connect('dev.db')
cur = conn.cursor()

# Check if agents table exists
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agents'")
if not cur.fetchone():
    print("❌ Agents table does not exist!")
    conn.close()
    exit(1)

# Insert sample agents
agents = [
    ('Main Agent', 'agent@crm.com', '+1234567890', 1),
    ('Sales Agent', 'sales@crm.com', '+1234567891', 1),
    ('Support Agent', 'support@crm.com', '+1234567892', 1),
]

try:
    for name, email, phone, is_active in agents:
        # Check if agent already exists
        cur.execute("SELECT id FROM agents WHERE email = ?", (email,))
        if cur.fetchone():
            print(f"⚠️  Agent {email} already exists, skipping...")
            continue
        
        # Insert agent
        cur.execute(
            """INSERT INTO agents (name, email, phone, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, email, phone, is_active, datetime.now(), datetime.now())
        )
        print(f"✅ Created agent: {name} ({email})")
    
    conn.commit()
    
    # Show all agents
    cur.execute("SELECT id, name, email, is_active FROM agents")
    rows = cur.fetchall()
    print(f"\n📋 Total agents in database: {len(rows)}")
    for row in rows:
        print(f"   ID: {row[0]}, Name: {row[1]}, Email: {row[2]}, Active: {bool(row[3])}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    conn.rollback()
finally:
    conn.close()
