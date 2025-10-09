"""Quick setup: Create customer, account and deposit."""
import httpx
import json

BASE_URL = "http://localhost:8000"

# 1. Login
print("1️⃣ Logging in...")
response = httpx.post(f"{BASE_URL}/auth/login", json={
    "email": "admin@example.com",
    "password": "admin"
})
if response.status_code != 200:
    print(f"❌ Login failed: {response.text}")
    exit(1)

token = response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("✅ Logged in!\n")

# 2. Create Customer
print("2️⃣ Creating customer...")
response = httpx.post(f"{BASE_URL}/api/customers", headers=headers, json={
    "name": "Test Customer",
    "email": "test@example.com",
    "phone": "+1234567890"
})
if response.status_code == 201:
    customer = response.json()
    print(f"✅ Customer created! ID: {customer['id']}\n")
else:
    print(f"❌ Failed: {response.text}")
    exit(1)

# 3. Create MT5 Account
print("3️⃣ Creating MT5 account...")
response = httpx.post(f"{BASE_URL}/api/accounts", headers=headers, json={
    "customer_id": customer['id'],
    "group": "test\\STD_USD",
    "leverage": 100,
    "currency": "USD",
    "password": "Test1234!",
    "name": "Test Customer"
})
if response.status_code == 201:
    account = response.json()
    login = account['login']
    print(f"✅ MT5 Account created! Login: {login}\n")
else:
    print(f"❌ Failed: {response.text}")
    exit(1)

# 4. Deposit
print("4️⃣ Making deposit...")
response = httpx.post(f"{BASE_URL}/api/balance", headers=headers, json={
    "login": login,
    "type": "deposit",
    "amount": 1000.0,
    "comment": "Initial deposit"
})
if response.status_code == 201:
    operation = response.json()
    print(f"✅ Deposit successful! Operation ID: {operation['id']}\n")
else:
    print(f"❌ Failed: {response.text}")
    exit(1)

# 5. Check Balance
print("5️⃣ Checking account...")
response = httpx.get(f"{BASE_URL}/api/accounts/{login}", headers=headers)
if response.status_code == 200:
    account = response.json()
    print(f"✅ Account Balance: ${account['balance']}")
    print(f"   Login: {account['login']}")
    print(f"   Group: {account['group']}")
    print(f"   Status: {account['status']}")
else:
    print(f"❌ Failed: {response.text}")

print("\n" + "="*50)
print("🎉 Setup Complete!")
print("="*50)
print(f"Customer ID: {customer['id']}")
print(f"MT5 Login: {login}")
print(f"Balance: $1000")
print("="*50)
