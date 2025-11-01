import sqlite3

conn = sqlite3.connect('dev.db')
cur = conn.cursor()

# Get total count
cur.execute('SELECT COUNT(*) FROM mt5_accounts')
total = cur.fetchone()[0]
print(f'✅ Total accounts in database: {total}')

# Check account 210502
cur.execute('SELECT id, login, name, balance, credit, "group", leverage, status FROM mt5_accounts WHERE login=210502')
row = cur.fetchone()

if row:
    print(f'\n📊 Account 210502 Details:')
    print(f'   ID: {row[0]}')
    print(f'   Login: {row[1]}')
    print(f'   Name: {row[2]}')
    print(f'   Balance: {row[3]}')
    print(f'   Credit: {row[4]}')
    print(f'   Group: {row[5]}')
    print(f'   Leverage: {row[6]}')
    print(f'   Status: {row[7]}')
else:
    print('❌ Account 210502 not found')

# Show a few more accounts
print(f'\n📋 Sample of other accounts:')
cur.execute('SELECT login, name, balance, credit FROM mt5_accounts LIMIT 5')
for row in cur.fetchall():
    print(f'   Login: {row[0]}, Name: {row[1]}, Balance: {row[2]}, Credit: {row[3]}')

conn.close()
