# CRM-MT5-Python

A dark-mode CRM system that integrates with MetaTrader 5 Manager SDK and Pipedrive for customer relationship management, account creation, balance operations, and bi-directional sync.

## Tech Stack

- **Backend**: FastAPI, uvicorn, SQLAlchemy 2.x
- **Database**: PostgreSQL (preferred) or SQLite for dev
- **Auth**: JWT (access + refresh), role-based (Admin, Dealer, Support, Viewer)
- **MT5 Integration**: Windows DLL interop via ctypes
- **Pipedrive Integration**: OAuth2/REST API + webhooks
- **UI**: Jinja2 + TailwindCSS (dark mode) + HTMX
- **Testing**: pytest, httpx AsyncClient

## Project Structure

```
/crm-mt5-python/
  ├── app/
  │   ├── main.py
  │   ├── settings.py
  │   ├── security.py
  │   ├── middleware.py
  │   ├── db.py
  │   ├── deps.py
  │   ├── alembic.ini
  │   ├── alembic/
  │   ├── domain/
  │   │   ├── models.py
  │   │   ├── enums.py
  │   │   └── dto.py
  │   ├── services/
  │   │   ├── mt5_manager.py
  │   │   ├── pipedrive.py
  │   │   ├── positions.py
  │   │   └── audit.py
  │   ├── repositories/
  │   ├── routers/
  │   └── ui/
  │       ├── templates/
  │       └── static/
  ├── scripts/
  │   ├── setup.ps1
  │   ├── run.ps1
  │   └── migrate.ps1
  ├── tests/
  ├── .env.example
  ├── requirements.txt
  └── pyproject.toml
```

## Setup (Windows)

### Prerequisites

- Python 3.10+
- PostgreSQL (optional, will use SQLite fallback)
- MT5 Manager SDK DLL
- Pipedrive account with API access

### Installation

1. Clone the repository and navigate to the project directory

2. Run the setup script:
```powershell
.\scripts\setup.ps1
```

This will:
- Create a Python virtual environment
- Install all dependencies
- Copy `.env.example` to `.env`
- Set up Tailwind CSS

3. Configure `.env` with your credentials:
- MT5 Manager SDK settings
- Pipedrive API credentials
- Database connection
- JWT secret key

4. Run database migrations:
```powershell
.\scripts\migrate.ps1
```

5. Start the application:
```powershell
.\scripts\run.ps1
```

The application will be available at `http://localhost:8000`

## Features

### Customer Management
- Create and manage customers
- Bi-directional sync with Pipedrive (Organizations/Persons)
- Link multiple MT5 accounts per customer
- Search and filter capabilities

### MT5 Account Operations
- Create MT5 accounts with custom parameters
- Reset passwords
- Move accounts between groups
- View account details and status

### Balance Operations
- Deposit/Withdrawal
- Credit In/Out
- Two-step confirmation
- Idempotency support
- Automatic Pipedrive notes

### Positions Monitoring
- Symbol-level net positions
- Open positions by account
- Real-time updates
- Visual dashboards

### Audit & Security
- Full audit trail for all operations
- JWT-based authentication
- Role-based access control (Admin, Dealer, Support, Viewer)
- Request ID tracking
- Structured logging

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login with email/password
- `POST /api/auth/refresh` - Refresh access token

### Customers
- `GET /api/customers` - List customers with search/filter
- `POST /api/customers` - Create new customer

### MT5 Accounts
- `GET /api/accounts` - List accounts by customer
- `POST /api/accounts` - Create new MT5 account
- `POST /api/accounts/{login}/reset-password` - Reset account password
- `POST /api/accounts/{login}/move-group` - Move account to different group
- `POST /api/accounts/{login}/balance` - Apply balance operation

### Positions
- `GET /api/positions/net` - Get net positions by symbol
- `GET /api/positions/open` - Get open positions by account

### Audit
- `GET /api/audit` - Get audit logs with pagination

### Webhooks
- `POST /webhooks/pipedrive` - Receive Pipedrive webhook events

### Health
- `GET /health` - Overall health check
- `GET /health/mt5` - MT5 connection health
- `GET /health/pipedrive` - Pipedrive connection health

## UI Pages

All pages feature a dark mode design by default with toggle support:

- **Sign In** - Email/password authentication
- **Dashboard** - KPIs, recent activities, charts
- **Customers** - List, create, search, detail view
- **Accounts** - MT5 account management
- **Balance** - Balance operations with confirmation
- **Positions** - Net and open positions monitoring
- **Settings** - User/role management, integrations health

## Development

### Running Tests
```powershell
.\.venv\Scripts\Activate.ps1
pytest tests/ -v
```

### Code Quality
Pre-commit hooks are configured for:
- Ruff (linting)
- Black (formatting)
- Trailing whitespace removal

Run manually:
```powershell
.\.venv\Scripts\Activate.ps1
pre-commit run --all-files
```

### Database Migrations

Create a new migration:
```powershell
.\.venv\Scripts\Activate.ps1
alembic revision --autogenerate -m "description"
```

Apply migrations:
```powershell
.\scripts\migrate.ps1
```

## Architecture

### MT5 Integration
- DLL wrapper using ctypes
- Connection pooling with auto-reconnect
- Retry logic with exponential backoff
- Circuit breaker pattern
- Error mapping and typed exceptions

### Pipedrive Integration
- OAuth2 flow with token storage
- REST API client with async httpx
- Webhook signature validation
- Bi-directional sync (push/pull)
- Rate limiting and retry handling

### Security
- JWT access + refresh tokens
- Password hashing with bcrypt
- Role-based authorization
- CORS configuration
- Input validation with Pydantic
- Idempotency key support

## License

Proprietary - All Rights Reserved
