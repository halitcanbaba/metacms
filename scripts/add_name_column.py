import sqlite3

conn = sqlite3.connect('dev.db')
try:
    conn.execute("ALTER TABLE mt5_accounts ADD COLUMN name VARCHAR(255) DEFAULT '' NOT NULL")
    conn.commit()
    print('✅ Name column added successfully to mt5_accounts table')
except Exception as e:
    print(f'Error: {e}')
finally:
    conn.close()
