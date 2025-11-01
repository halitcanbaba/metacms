"""MetaTrader 5 Manager API service using official MT5Manager Python package."""
import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Any
import structlog
import MT5Manager
from app.settings import settings

logger = structlog.get_logger()

class MT5Exception(Exception):
    def __init__(self, message: str, code: int | None = None):
        self.message = message
        self.code = code
        super().__init__(f"MT5 Error {code}: {message}" if code else message)

class MT5ConnectionError(MT5Exception):
    pass

class MT5InvalidDataError(MT5Exception):
    pass

@dataclass
class Mt5AccountInfo:
    login: int
    group: str
    leverage: int
    currency: str
    balance: float
    credit: float
    equity: float
    margin_free: float
    margin_level: float
    status: str
    name: str = ""  # Account name from MT5

@dataclass
class Mt5BalanceResult:
    success: bool
    deal_id: int | None = None
    error: str | None = None

@dataclass
class Mt5DailyReport:
    """Daily report containing account state for a specific date."""
    login: int
    date: str  # YYYY-MM-DD format
    balance: float
    credit: float
    equity_prev_day: float  # Previous day equity
    equity_prev_month: float  # Previous month equity
    balance_prev_day: float  # Previous day balance
    balance_prev_month: float  # Previous month balance
    margin: float
    margin_free: float
    margin_level: float
    margin_leverage: int
    floating_profit: float
    group: str
    currency: str
    currency_digits: int
    timestamp: int  # Unix timestamp of the report
    datetime_prev: int  # Previous day timestamp
    
    # Account info
    name: str
    email: str
    company: str
    
    # Agent commissions
    agent_daily: float
    agent_monthly: float
    commission_daily: float
    commission_monthly: float
    
    # Daily transactions breakdown
    daily_balance: float  # Balance operations (deposits/withdrawals)
    daily_credit: float  # Credit operations
    daily_charge: float  # Charges
    daily_correction: float  # Corrections
    daily_bonus: float  # Bonuses
    daily_comm_fee: float  # Commission fees
    daily_comm_instant: float  # Instant commissions
    daily_comm_round: float  # Round commissions
    daily_interest: float  # Interest
    daily_dividend: float  # Dividends
    daily_profit: float  # Closed profit
    daily_storage: float  # Storage/swap
    daily_agent: float  # Agent operations
    daily_so_compensation: float  # Stop-out compensation
    daily_so_compensation_credit: float  # Stop-out compensation credit
    daily_taxes: float  # Taxes
    
    # Interest rate
    interest_rate: float
    
    # Profit breakdown
    present_equity: float  # Current/present equity (floating profit)
    profit_storage: float  # Storage profit
    profit_assets: float  # Assets profit
    profit_liabilities: float  # Liabilities profit

@dataclass
class Mt5RealtimeEquity:
    """Realtime equity information for an account."""
    login: int
    name: str
    balance: float
    credit: float
    equity: float
    net_equity: float  # Equity - Credit (pure account value without credit)
    margin: float
    margin_free: float
    margin_level: float
    floating_profit: float
    group: str
    currency: str
    timestamp: int  # Unix timestamp when fetched

@dataclass
class Mt5DealHistory:
    """Deal history record for deposits, withdrawals, and credits."""
    deal_id: int
    login: int
    action: str  # 'DEPOSIT', 'WITHDRAWAL', 'CREDIT', 'CREDIT_OUT', 'BONUS'
    amount: float
    balance_after: float
    comment: str
    timestamp: int  # Unix timestamp
    datetime_str: str  # Human-readable datetime
    tag: str = ""  # Tag for special deal types (e.g., 'Rebate' for REB comments)

@dataclass
class NetPositionSummary:
    symbol: str
    buy_volume: float
    sell_volume: float
    net_volume: float
    positions_count: int
    total_profit: float = 0.0

@dataclass
class Mt5DailyPnL:
    """Daily PNL calculation for an account."""
    login: int
    date: str  # YYYY-MM-DD format
    present_equity: float  # Current day equity (from daily report)
    equity_prev_day: float  # Previous day equity (from daily report)
    deposit: float = 0.0  # Total deposits for the day (DT-tagged deals)
    withdrawal: float = 0.0  # Total withdrawals for the day (WT-tagged deals)
    net_deposit: float = 0.0  # Net deposits for the day (deposits - withdrawals)
    credit: float = 0.0  # Credit operations for the day (CREDIT action)
    promotion: float = 0.0  # Promotion amount for the day (non-DT/WT/REB tagged deals)
    net_credit_promotion: float = 0.0  # Net credit/promotions for the day
    total_ib: float = 0.0  # Total IB commissions for the day (from daily_agent field)
    rebate: float = 0.0  # Total rebate for the day (from REB-tagged deals)
    equity_pnl: float = 0.0  # Calculated: present_equity - equity_prev_day - net_deposit - net_credit_promotion - total_ib
    net_pnl: float = 0.0  # Calculated: equity_pnl - promotion
    group: str = ""
    currency: str = ""

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "closed"

    def call_failed(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"

    def call_succeeded(self):
        self.failure_count = 0
        self.state = "closed"

    def can_execute(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.time() - self.last_failure_time >= self.timeout:
                self.state = "half_open"
                return True
            return False
        return True

class MT5ManagerService:
    def __init__(self):
        self.manager: MT5Manager.ManagerAPI | None = None
        self.connected = False
        self.circuit_breaker = CircuitBreaker()
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        async with self._lock:
            if self.connected:
                return True
            if not self.circuit_breaker.can_execute():
                raise MT5ConnectionError("Circuit breaker is open")
            try:
                if self.manager is None:
                    self.manager = MT5Manager.ManagerAPI()
                server_address = f"{settings.mt5_manager_host}:{settings.mt5_manager_port}"
                logger.info("mt5_connecting", server=server_address)
                def _connect():
                    # Enable pumping for users AND positions
                    pump_mode = (
                        MT5Manager.ManagerAPI.EnPumpModes.PUMP_MODE_USERS |
                        MT5Manager.ManagerAPI.EnPumpModes.PUMP_MODE_POSITIONS
                    )
                    return self.manager.Connect(
                        server_address,
                        settings.mt5_manager_login,
                        settings.mt5_manager_password,
                        pump_mode,
                        120000
                    )
                result = await asyncio.get_event_loop().run_in_executor(None, _connect)
                if not result:
                    error = MT5Manager.LastError()
                    code_value = error[1].value if hasattr(error[1], "value") else error[1]
                    raise MT5ConnectionError(f"Connection failed: {error[2]}", code=code_value)
                self.connected = True
                self.circuit_breaker.call_succeeded()
                logger.info("mt5_connected", server=server_address)
                return True
            except Exception as e:
                self.circuit_breaker.call_failed()
                logger.error("mt5_connection_error", error=str(e))
                raise MT5ConnectionError(f"Failed to connect: {e}")

    async def disconnect(self):
        async with self._lock:
            if not self.connected:
                return
            try:
                if self.manager:
                    await asyncio.get_event_loop().run_in_executor(None, self.manager.Disconnect)
                self.connected = False
            except Exception as e:
                logger.error("mt5_disconnection_failed", error=str(e))

    async def _execute_with_retry(self, func, *args, **kwargs):
        last_exception = None
        for attempt in range(settings.mt5_max_retries):
            try:
                if not self.connected:
                    await self.connect()
                result = await asyncio.get_event_loop().run_in_executor(None, func, *args, **kwargs)
                self.circuit_breaker.call_succeeded()
                return result
            except Exception as e:
                last_exception = e
                if attempt < settings.mt5_max_retries - 1:
                    await asyncio.sleep(2**attempt)
                    self.connected = False
                self.circuit_breaker.call_failed()
        raise MT5Exception(f"Operation failed after {settings.mt5_max_retries} retries: {last_exception}")

    async def create_account(self, group: str, leverage: int, currency: str, password: str, name: str = "") -> Mt5AccountInfo:
        def _create():
            # Find the highest existing login number across ALL users (not just the group)
            # This prevents login conflicts when creating accounts in different groups
            max_login = 0
            try:
                # Get ALL users from MT5 using wildcard
                all_users = self.manager.UserGetByGroup("*")
                if all_users and len(all_users) > 0:
                    # Find the absolute max login across ALL users
                    max_login = max(u.Login for u in all_users)
                    
                    # Also log group-specific info for debugging
                    group_users = [u for u in all_users if hasattr(u, 'Group') and u.Group == group]
                    logger.info("found_max_login", 
                              group=group, 
                              max_login=max_login, 
                              next_login=max_login + 1,
                              group_users=len(group_users), 
                              total_users=len(all_users))
                else:
                    logger.info("no_users_in_system")
            except Exception as e:
                logger.warning("could_not_get_max_login", error=str(e), group=group)
            
            # Create new user with next available login
            user = MT5Manager.MTUser(self.manager)
            
            # Always set the login - use next available number
            # If max_login is 0 (no users), MT5 will auto-assign
            if max_login > 0:
                user.Login = max_login + 1
                logger.info("setting_login", login=user.Login, group=group)
            else:
                logger.info("no_login_set_mt5_will_auto_assign", group=group)
                
            user.Group = group
            user.Leverage = leverage
            
            # Use full name only for FirstName, LastName stays empty
            # MT5 will display just the full name from FirstName
            full_name = name.strip() if name else "User Account"
            user.FirstName = full_name
            user.LastName = ""
            
            # Set user rights: Enable the account and allow trading
            # USER_RIGHT_ENABLED (1) + USER_RIGHT_PASSWORD (2) + USER_RIGHT_CONFIRMED (16) 
            # + USER_RIGHT_EXPERT (64) + USER_RIGHT_REPORTS (256) = 339
            user.Rights = (
                MT5Manager.MTUser.EnUsersRights.USER_RIGHT_ENABLED |
                MT5Manager.MTUser.EnUsersRights.USER_RIGHT_PASSWORD |
                MT5Manager.MTUser.EnUsersRights.USER_RIGHT_CONFIRMED |
                MT5Manager.MTUser.EnUsersRights.USER_RIGHT_EXPERT |
                MT5Manager.MTUser.EnUsersRights.USER_RIGHT_REPORTS
            )
            
            if not self.manager.UserAdd(user, password, password):
                error = MT5Manager.LastError()
                attempted_login = user.Login if max_login > 0 else "auto"
                raise MT5Exception(
                    f"Account creation failed: {error[2]} (attempted login: {attempted_login}, max_login: {max_login})", 
                    error[1].value
                )
            
            logger.info("account_created_with_login", login=user.Login, group=group, leverage=leverage, rights=user.Rights)
            
            # MTUser doesn't have MarginFree/MarginLevel/Equity - use defaults for new account
            # These values are only available via UserAccountGet after trading starts
            return Mt5AccountInfo(
                login=user.Login, 
                group=user.Group, 
                leverage=user.Leverage, 
                currency=currency,
                balance=user.Balance, 
                credit=user.Credit,
                equity=user.Balance + user.Credit,  # For new account, equity = balance + credit
                margin_free=0.0,  # New account has no margin usage
                margin_level=0.0,  # New account has no margin level
                status="active",
                name=full_name
            )
        return await self._execute_with_retry(_create)

    async def reset_password(self, login: int, new_password: str) -> None:
        def _reset():
            if not self.manager.UserPasswordChange(MT5Manager.MTUser.EnUsersPasswords.USER_PASS_MAIN, login, new_password):
                error = MT5Manager.LastError()
                raise MT5Exception(f"Password reset failed: {error[2]}", error[1].value)
        await self._execute_with_retry(_reset)

    async def move_to_group(self, login: int, group_name: str) -> None:
        def _move():
            user = self.manager.UserRequest(login)
            if user is False:
                error = MT5Manager.LastError()
                raise MT5Exception(f"User not found: {error[2]}", error[1].value)
            user.Group = group_name
            if not self.manager.UserUpdate(user):
                error = MT5Manager.LastError()
                raise MT5Exception(f"Group move failed: {error[2]}", error[1].value)
        await self._execute_with_retry(_move)

    async def get_groups(self) -> list[dict[str, Any]]:
        """Get all available groups from MT5 server by extracting from all users."""
        def _get_groups():
            try:
                logger.info("fetching_all_users_to_extract_groups")
                
                # Get all users from MT5 using wildcard
                users = self.manager.UserGetByGroup("*")
                
                if users is False or users is None:
                    error = MT5Manager.LastError()
                    logger.error("user_get_by_group_failed", error=error)
                    raise MT5Exception(f"Failed to get users: {error[2] if error else 'Unknown error'}")
                
                if not users or len(users) == 0:
                    logger.warning("no_users_found")
                    return []
                
                logger.info("users_fetched", total_users=len(users))
                
                # Extract unique groups from users
                unique_groups = set()
                for user in users:
                    if hasattr(user, 'Group') and user.Group:
                        unique_groups.add(user.Group)
                
                logger.info("unique_groups_extracted", count=len(unique_groups), groups=list(unique_groups))
                
                # Convert to response format
                result = []
                for group_name in sorted(unique_groups):
                    result.append({
                        "name": group_name,
                        "server": None,
                        "currency": None,
                        "company": None,
                    })
                
                return result
                
            except Exception as e:
                logger.error("get_groups_exception", error=str(e), error_type=type(e).__name__)
                raise MT5Exception(f"Failed to get groups: {str(e)}")
        
        return await self._execute_with_retry(_get_groups)

    async def apply_balance_operation(self, login: int, op_type: str, amount: float, comment: str = "") -> Mt5BalanceResult:
        def _apply():
            if op_type in ("deposit", "withdrawal"):
                deal_action = MT5Manager.MTDeal.EnDealAction.DEAL_BALANCE
                # For withdrawal, amount should be negative
                if op_type == "withdrawal":
                    amount_to_apply = -abs(amount)
                else:  # deposit
                    amount_to_apply = abs(amount)
            elif op_type in ("credit_in", "credit_out"):
                deal_action = MT5Manager.MTDeal.EnDealAction.DEAL_CREDIT
                # For credit_out, amount should be negative
                if op_type == "credit_out":
                    amount_to_apply = -abs(amount)
                else:  # credit_in
                    amount_to_apply = abs(amount)
            else:
                raise MT5InvalidDataError(f"Invalid operation type: {op_type}")
            
            deal_id = self.manager.DealerBalance(login, amount_to_apply, deal_action, comment)
            if deal_id is False:
                error = MT5Manager.LastError()
                raise MT5Exception(f"Balance operation failed: {error[2]}", error[1].value)
            return Mt5BalanceResult(success=True, deal_id=deal_id)
        return await self._execute_with_retry(_apply)

    async def get_net_positions(self, symbol_filter: str | None = None) -> list[NetPositionSummary]:
        def _get_positions():
            # Get positions by requesting from all groups
            # PositionGetByGroup gets all positions for groups matching pattern
            positions = self.manager.PositionGetByGroup("*")  # All groups
            
            # Debug logging
            logger.info("mt5_position_getbygroup_result", 
                       group="*",
                       result_type=type(positions).__name__ if positions else "None",
                       is_false=positions is False,
                       is_none=positions is None,
                       length=len(positions) if positions and positions is not False else 0)
            
            if positions is False or positions is None or len(positions) == 0:
                error = MT5Manager.LastError()
                logger.warning("mt5_position_get_failed", error_code=error[1].value if error else None, error_msg=error[2] if error else None)
                return []
            
            # Aggregate positions by symbol
            symbol_data = {}
            for pos in positions:
                try:
                    symbol = pos.Symbol
                    
                    # Skip empty symbols
                    if not symbol or symbol.strip() == '':
                        continue
                    
                    # Apply symbol filter if provided
                    if symbol_filter and "*" in symbol_filter:
                        pattern = symbol_filter.replace("*", "")
                        if not symbol.startswith(pattern):
                            continue
                    elif symbol_filter and symbol != symbol_filter:
                        continue
                    
                    # Initialize symbol data if not exists
                    if symbol not in symbol_data:
                        symbol_data[symbol] = {
                            "buy_volume": 0.0, 
                            "sell_volume": 0.0, 
                            "count": 0,
                            "total_profit": 0.0
                        }
                    
                    # Get volume in lots (MT5 stores in 10000ths)
                    volume_lots = pos.Volume / 10000.0
                    
                    # Get profit (including swap and commission if available)
                    profit = pos.Profit
                    if hasattr(pos, 'Storage'):
                        profit += pos.Storage  # Add swap
                    
                    # Aggregate by action (buy/sell)
                    if pos.Action == MT5Manager.MTPosition.EnPositionAction.POSITION_BUY:
                        symbol_data[symbol]["buy_volume"] += volume_lots
                    else:  # POSITION_SELL
                        symbol_data[symbol]["sell_volume"] += volume_lots
                    
                    symbol_data[symbol]["count"] += 1
                    symbol_data[symbol]["total_profit"] += profit
                    
                    logger.debug("position_processed", 
                                login=pos.Login,
                                symbol=symbol, 
                                action="buy" if pos.Action == MT5Manager.MTPosition.EnPositionAction.POSITION_BUY else "sell",
                                volume=volume_lots,
                                profit=profit)
                    
                except Exception as e:
                    logger.error("position_parse_error", error=str(e))
                    continue
            
            # Convert aggregated data to result list
            result = [
                NetPositionSummary(
                    symbol=sym,
                    buy_volume=data["buy_volume"],
                    sell_volume=data["sell_volume"],
                    net_volume=data["buy_volume"] - data["sell_volume"],
                    positions_count=data["count"],
                    total_profit=data["total_profit"]
                )
                for sym, data in symbol_data.items()
            ]
            
            logger.info("positions_aggregated", 
                       total_symbols=len(result), 
                       total_positions=sum(p.positions_count for p in result),
                       total_profit=sum(p.total_profit for p in result))
            
            return result
        return await self._execute_with_retry(_get_positions)

    async def get_all_positions(self) -> list[dict]:
        """Get all open positions across all accounts."""
        return await self.get_positions_by_login(login=None)
    
    async def get_positions_by_login(self, login: int | None = None, symbol_filter: str | None = None) -> list[dict]:
        """Get all open positions for a specific login or all positions."""
        def _get_positions():
            # Get all positions
            positions = self.manager.PositionGetByGroup("*")
            
            if positions is False or positions is None or len(positions) == 0:
                return []
            
            result = []
            for pos in positions:
                try:
                    # Filter by login if specified
                    if login is not None and pos.Login != login:
                        continue
                    
                    # Filter by symbol if specified
                    if symbol_filter is not None and pos.Symbol != symbol_filter:
                        continue
                    
                    # Convert volume from MT5 format (10000ths) to lots
                    volume_lots = pos.Volume / 10000.0
                    
                    # Get position details
                    position_data = {
                        "ticket": pos.Position,
                        "login": pos.Login,
                        "symbol": pos.Symbol,
                        "volume": volume_lots,
                        "action": pos.Action,  # 0=buy, 1=sell
                        "price_open": pos.PriceOpen,
                        "price_current": pos.PriceCurrent,
                        "profit": pos.Profit,
                        "swap": pos.Storage,
                        "commission": pos.Commission if hasattr(pos, 'Commission') else 0.0,
                        "time_create": pos.TimeCreate,
                    }
                    
                    result.append(position_data)
                    
                except Exception as e:
                    logger.error("position_parse_error", error=str(e), login=login)
                    continue
            
            # Only log if not frequently called (commented for WebSocket performance)
            # logger.info("positions_retrieved_by_login", login=login, symbol=symbol_filter, count=len(result))
            
            return result
        
        return await self._execute_with_retry(_get_positions)

    async def get_position_history(
        self,
        login: int | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict]:
        """
        Get closed position history for an account.
        
        Args:
            login: Specific account login (required)
            from_date: Start date for history
            to_date: End date for history
            
        Returns:
            List of closed position dicts with details
        """
        if not self.connected:
            await self.connect()
        
        def _get_history():
            logger.info("fetching_position_history", login=login, from_date=from_date, to_date=to_date)
            
            # Convert dates to timestamps
            if from_date:
                from_ts = int(datetime.combine(from_date, datetime.min.time()).timestamp())
            else:
                from_ts = int((datetime.now() - timedelta(days=30)).timestamp())
            
            if to_date:
                to_ts = int(datetime.combine(to_date, datetime.max.time()).timestamp())
            else:
                to_ts = int(datetime.now().timestamp())
            
            # Get closed positions from MT5 using DealRequest
            if login is None:
                logger.error("position_history_requires_login")
                return []
            
            # Use DealRequest to get all deals (including closes)
            deals = self.manager.DealRequest(login, from_ts, to_ts)
            
            if deals is False or not deals:
                error = MT5Manager.LastError()
                logger.error("deal_request_failed", error=error)
                return []
            
            logger.info("deals_received", total=len(deals))
            
            # Group deals by position to find closed positions
            # Entry: 0=IN (open), 1=OUT (close), 2=INOUT (instant close)
            position_map = {}
            result = []
            
            for deal in deals:
                try:
                    # Get deal details
                    position_id = deal.Position if hasattr(deal, 'Position') else 0
                    deal_id = deal.Deal if hasattr(deal, 'Deal') else 0
                    order_id = deal.Order if hasattr(deal, 'Order') else 0
                    symbol = deal.Symbol if hasattr(deal, 'Symbol') else ""
                    action_code = deal.Action if hasattr(deal, 'Action') else None
                    entry_code = deal.Entry if hasattr(deal, 'Entry') else None
                    
                    # Log for debugging
                    logger.debug("deal_record", 
                                deal_id=deal_id, 
                                position_id=position_id,
                                action=action_code, 
                                entry=entry_code,
                                symbol=symbol)
                    
                    # Skip if not a market deal (Entry: 0=IN, 1=OUT, 2=INOUT)
                    # We want closed positions (OUT or INOUT)
                    if entry_code not in [1, 2]:
                        continue
                    
                    # Determine action type
                    # Action: 0=BUY, 1=SELL for deals
                    action_name = 'BUY' if action_code == 0 else 'SELL' if action_code == 1 else 'UNKNOWN'
                    
                    volume = deal.Volume / 10000.0 if hasattr(deal, 'Volume') else 0.0
                    price = deal.Price if hasattr(deal, 'Price') else 0.0
                    profit = deal.Profit if hasattr(deal, 'Profit') else 0.0
                    commission = deal.Commission if hasattr(deal, 'Commission') else 0.0
                    swap = deal.Storage if hasattr(deal, 'Storage') else 0.0
                    timestamp = deal.Time if hasattr(deal, 'Time') else 0
                    
                    # Format datetime
                    if timestamp:
                        utc_time = datetime.utcfromtimestamp(timestamp)
                        datetime_str = utc_time.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        datetime_str = ""
                    
                    # Get open and close times
                    time_create = deal.TimeCreate if hasattr(deal, 'TimeCreate') else 0
                    time_create_str = ""
                    if time_create:
                        time_create_str = datetime.utcfromtimestamp(time_create).strftime('%Y-%m-%d %H:%M:%S')
                    
                    result.append({
                        "position_id": position_id,
                        "deal_id": deal_id,
                        "order_id": order_id,
                        "login": login,
                        "symbol": symbol,
                        "action": action_name,
                        "volume": volume,
                        "price": price,
                        "profit": profit,
                        "commission": commission,
                        "swap": swap,
                        "timestamp": timestamp,
                        "datetime": datetime_str,
                        "time_create": time_create,
                        "time_create_str": time_create_str,
                    })
                except Exception as e:
                    logger.warning("failed_to_parse_position_history", error=str(e))
                    continue
            
            logger.info("position_history_filtered", total=len(result))
            return result
        
        return await self._execute_with_retry(_get_history)

    async def get_account_info(self, login: int) -> Mt5AccountInfo:
        def _get_info():
            # Get user basic info
            user = self.manager.UserRequest(login)
            if user is False:
                error = MT5Manager.LastError()
                raise MT5Exception(f"User not found: {error[2]}", error[1].value)
            
            # Try to get trading account info for margin details
            margin_free = 0.0
            margin_level = 0.0
            try:
                account = self.manager.UserAccountGet(login)
                if account and account is not False:
                    margin_free = account.MarginFree if hasattr(account, 'MarginFree') else 0.0
                    margin_level = account.MarginLevel if hasattr(account, 'MarginLevel') else 0.0
            except:
                # If UserAccountGet fails, use defaults
                pass
            
            # Calculate equity: balance + credit + floating P&L
            # Get positions to calculate floating P&L
            floating_pnl = 0.0
            try:
                positions = self.manager.PositionRequestByLogin(login)
                if positions and positions is not False:
                    for pos in positions:
                        if hasattr(pos, 'Profit'):
                            floating_pnl += pos.Profit
            except:
                pass
            
            balance = user.Balance if hasattr(user, 'Balance') else 0.0
            credit = user.Credit if hasattr(user, 'Credit') else 0.0
            equity = balance + credit + floating_pnl
            name = user.Name if hasattr(user, 'Name') else ""
            
            return Mt5AccountInfo(
                login=user.Login, 
                group=user.Group, 
                leverage=user.Leverage, 
                currency="USD",
                balance=balance, 
                credit=credit,
                equity=equity,
                margin_free=margin_free,
                margin_level=margin_level, 
                status="active",
                name=name
            )
        return await self._execute_with_retry(_get_info)

    async def get_daily_reports(
        self, 
        login: int | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        group: str | None = None,
    ) -> list[Mt5DailyReport]:
        """
        Get daily reports for accounts.
        
        Args:
            login: Specific account login (optional)
            from_date: Start date for report range
            to_date: End date for report range
            group: Group pattern for filtering (optional, e.g. "demo\\*")
        
        Returns:
            List of daily reports with equity and balance information
        """
        def _get_daily_reports():
            # Convert dates to UTC timestamps
            # MT5 Manager API expects UTC timestamps
            # API dates are treated as UTC dates
            
            if from_date:
                # Create datetime in UTC (treat date as UTC, not local)
                utc_dt = datetime.combine(from_date, datetime.min.time())
                # Calculate timestamp as if this datetime was UTC
                from_timestamp = int((utc_dt - datetime(1970, 1, 1)).total_seconds())
            else:
                # Default to yesterday
                yesterday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                from_timestamp = int((yesterday - timedelta(days=1)).timestamp())
            
            if to_date:
                # End of day in UTC
                utc_dt = datetime.combine(to_date, datetime.max.time())
                to_timestamp = int((utc_dt - datetime(1970, 1, 1)).total_seconds())
            else:
                # Default to now
                to_timestamp = int(datetime.now().timestamp())
            
            logger.info("fetching_daily_reports", 
                       login=login, 
                       from_date=from_date, 
                       to_date=to_date,
                       from_timestamp=from_timestamp,
                       to_timestamp=to_timestamp,
                       group=group)
            
            # Choose appropriate API call based on parameters
            if login:
                # Try DailyRequestByLogins first (more efficient for single login)
                logger.info("calling_daily_request_by_logins", login=login)
                try:
                    reports = self.manager.DailyRequestByLogins([login], from_timestamp, to_timestamp)
                    logger.info("daily_request_by_logins_response", 
                               success=reports is not False,
                               reports_type=type(reports).__name__ if reports else None)
                except Exception as e:
                    logger.warning("daily_request_by_logins_failed", error=str(e), error_type=type(e).__name__)
                    # Fallback to DailyRequestLight
                    logger.info("calling_daily_request_light_fallback", login=login)
                    reports = self.manager.DailyRequestLight(login, from_timestamp, to_timestamp)
            elif group:
                # Get reports by group pattern
                logger.info("calling_daily_request_light_by_group", group=group)
                reports = self.manager.DailyRequestLightByGroup(group, from_timestamp, to_timestamp)
            else:
                # Get reports for all accounts (using wildcard group)
                logger.info("calling_daily_request_light_by_group_all")
                reports = self.manager.DailyRequestLightByGroup("*", from_timestamp, to_timestamp)
            
            logger.info("daily_reports_raw_response", 
                       reports_type=type(reports).__name__,
                       reports_is_false=reports is False,
                       reports_is_none=reports is None,
                       reports_bool=bool(reports) if reports is not False else False)
            
            if reports is False:
                error = MT5Manager.LastError()
                error_code = error[1].value if error and len(error) > 1 else None
                error_msg = error[2] if error and len(error) > 2 else "Unknown error"
                logger.error("daily_reports_api_returned_false", 
                           error=error, 
                           error_code=error_code,
                           error_message=error_msg)
                return []
            
            if reports is None:
                logger.warning("daily_reports_api_returned_none")
                return []
            
            reports_len = len(reports) if reports else 0
            logger.info("daily_reports_received", total=reports_len)
            
            if not reports or reports_len == 0:
                logger.info("no_daily_reports_found_in_response")
                return []
            
            # Parse reports into dataclass
            result = []
            for idx, report in enumerate(reports):
                try:
                    # Log all available attributes for debugging
                    if idx == 0:  # Log only first report to avoid spam
                        available_attrs = [attr for attr in dir(report) if not attr.startswith('_')]
                        logger.info("mt5_daily_report_available_fields", 
                                   fields=available_attrs,
                                   sample_values={attr: getattr(report, attr, None) for attr in available_attrs[:20]})
                    
                    # Extract date from timestamp - try multiple field names
                    date_value = None
                    date_field_used = None
                    for date_field in ['Datetime', 'DateTime', 'DatetimeDay', 'Date', 'DailyDate']:
                        if hasattr(report, date_field):
                            date_value = getattr(report, date_field)
                            if date_value and date_value > 0:
                                date_field_used = date_field
                                break
                    
                    if not date_value:
                        logger.warning("report_missing_datetime", index=idx, 
                                     has_datetime=hasattr(report, 'DateTime'),
                                     has_datetime_lower=hasattr(report, 'Datetime'))
                        continue
                    
                    # MT5 Manager API returns UTC timestamps for the reporting date
                    # Parse directly as UTC without adjustment
                    utc_time = datetime.utcfromtimestamp(date_value)
                    report_date = utc_time.strftime('%Y-%m-%d')
                    
                    # Get balance and equity fields from MT5 Daily Report
                    balance = report.Balance if hasattr(report, 'Balance') else 0.0
                    credit = report.Credit if hasattr(report, 'Credit') else 0.0
                    
                    # Get current equity (ProfitEquity = floating equity)
                    profit_equity = report.ProfitEquity if hasattr(report, 'ProfitEquity') else 0.0
                    equity = balance + credit + profit_equity
                    
                    # Get previous day/month equity and balance
                    equity_prev_day = report.EquityPrevDay if hasattr(report, 'EquityPrevDay') else 0.0
                    equity_prev_month = report.EquityPrevMonth if hasattr(report, 'EquityPrevMonth') else 0.0
                    balance_prev_day = report.BalancePrevDay if hasattr(report, 'BalancePrevDay') else 0.0
                    balance_prev_month = report.BalancePrevMonth if hasattr(report, 'BalancePrevMonth') else 0.0
                    
                    # Floating profit
                    floating_profit = report.Profit if hasattr(report, 'Profit') else 0.0
                    
                    result.append(Mt5DailyReport(
                        login=report.Login,
                        date=report_date,
                        balance=balance,
                        credit=credit,
                        equity_prev_day=equity_prev_day,
                        equity_prev_month=equity_prev_month,
                        balance_prev_day=balance_prev_day,
                        balance_prev_month=balance_prev_month,
                        margin=report.Margin if hasattr(report, 'Margin') else 0.0,
                        margin_free=report.MarginFree if hasattr(report, 'MarginFree') else 0.0,
                        margin_level=report.MarginLevel if hasattr(report, 'MarginLevel') else 0.0,
                        margin_leverage=int(report.MarginLeverage) if hasattr(report, 'MarginLeverage') else 0,
                        floating_profit=floating_profit,
                        group=report.Group if hasattr(report, 'Group') else "",
                        currency=report.Currency if hasattr(report, 'Currency') else "USD",
                        currency_digits=int(report.CurrencyDigits) if hasattr(report, 'CurrencyDigits') else 2,
                        timestamp=date_value,
                        datetime_prev=int(report.DatetimePrev) if hasattr(report, 'DatetimePrev') else 0,
                        
                        # Account info
                        name=report.Name if hasattr(report, 'Name') else "",
                        email=report.EMail if hasattr(report, 'EMail') else "",
                        company=report.Company if hasattr(report, 'Company') else "",
                        
                        # Agent commissions
                        agent_daily=report.AgentDaily if hasattr(report, 'AgentDaily') else 0.0,
                        agent_monthly=report.AgentMonthly if hasattr(report, 'AgentMonthly') else 0.0,
                        commission_daily=report.CommissionDaily if hasattr(report, 'CommissionDaily') else 0.0,
                        commission_monthly=report.CommissionMonthly if hasattr(report, 'CommissionMonthly') else 0.0,
                        
                        # Daily transactions breakdown
                        daily_balance=report.DailyBalance if hasattr(report, 'DailyBalance') else 0.0,
                        daily_credit=report.DailyCredit if hasattr(report, 'DailyCredit') else 0.0,
                        daily_charge=report.DailyCharge if hasattr(report, 'DailyCharge') else 0.0,
                        daily_correction=report.DailyCorrection if hasattr(report, 'DailyCorrection') else 0.0,
                        daily_bonus=report.DailyBonus if hasattr(report, 'DailyBonus') else 0.0,
                        daily_comm_fee=report.DailyCommFee if hasattr(report, 'DailyCommFee') else 0.0,
                        daily_comm_instant=report.DailyCommInstant if hasattr(report, 'DailyCommInstant') else 0.0,
                        daily_comm_round=report.DailyCommRound if hasattr(report, 'DailyCommRound') else 0.0,
                        daily_interest=report.DailyInterest if hasattr(report, 'DailyInterest') else 0.0,
                        daily_dividend=report.DailyDividend if hasattr(report, 'DailyDividend') else 0.0,
                        daily_profit=report.DailyProfit if hasattr(report, 'DailyProfit') else 0.0,
                        daily_storage=report.DailyStorage if hasattr(report, 'DailyStorage') else 0.0,
                        daily_agent=report.DailyAgent if hasattr(report, 'DailyAgent') else 0.0,
                        daily_so_compensation=report.DailySOCompensation if hasattr(report, 'DailySOCompensation') else 0.0,
                        daily_so_compensation_credit=report.DailySOCompensationCredit if hasattr(report, 'DailySOCompensationCredit') else 0.0,
                        daily_taxes=report.DailyTaxes if hasattr(report, 'DailyTaxes') else 0.0,
                        
                        # Interest rate
                        interest_rate=report.InterestRate if hasattr(report, 'InterestRate') else 0.0,
                        
                        # Profit breakdown
                        present_equity=profit_equity,
                        profit_storage=report.ProfitStorage if hasattr(report, 'ProfitStorage') else 0.0,
                        profit_assets=report.ProfitAssets if hasattr(report, 'ProfitAssets') else 0.0,
                        profit_liabilities=report.ProfitLiabilities if hasattr(report, 'ProfitLiabilities') else 0.0,
                    ))
                except Exception as e:
                    logger.warning("failed_to_parse_daily_report", error=str(e), index=idx)
                    continue
            
            logger.info("daily_reports_fetched", total_reports=len(result))
            return result
        
        return await self._execute_with_retry(_get_daily_reports)

    async def get_realtime_accounts(
        self, 
        login: int | None = None,
        group: str | None = None
    ) -> list[Mt5RealtimeEquity]:
        """
        Get realtime account information.
        
        Args:
            login: Specific account login (optional)
            group: Group pattern filter (optional, e.g., "test\\*")
            
        Returns:
            List of Mt5RealtimeEquity with current account states
        """
        if not self.connected:
            await self.connect()
        
        def _get_realtime():
            # Only log if not frequently called (commented for WebSocket performance)
            # logger.info("fetching_realtime_accounts", login=login, group=group)
            
            # Get list of users to process
            users = []
            if login is not None:
                # Single user
                user = self.manager.UserRequest(login)
                if user is False:
                    error = MT5Manager.LastError()
                    error_msg = error[2] if error and len(error) > 2 else "User not found"
                    error_code = error[1].value if error and len(error) > 1 else None
                    logger.error("user_request_failed", login=login, error=error_msg, code=error_code)
                    raise MT5Exception(f"User not found: {error_msg}", error_code)
                users = [user]
            else:
                # Get users by group pattern
                group_pattern = group if group else "*"
                users_result = self.manager.UserGetByGroup(group_pattern)
                if users_result is False:
                    error = MT5Manager.LastError()
                    logger.error("users_get_by_group_failed", group=group_pattern, error=error)
                    return []
                users = users_result if users_result else []
            
            # Only log if not frequently called (commented for WebSocket performance)
            # logger.info("processing_users", total=len(users))
            
            # Process each user
            result = []
            current_time = int(time.time())
            
            for user in users:
                try:
                    user_login = user.Login if hasattr(user, 'Login') else None
                    if not user_login:
                        continue
                    
                    user_name = user.Name if hasattr(user, 'Name') else ""
                    balance = user.Balance if hasattr(user, 'Balance') else 0.0
                    credit = user.Credit if hasattr(user, 'Credit') else 0.0
                    user_group = user.Group if hasattr(user, 'Group') else ""
                    currency = getattr(user, 'Currency', 'USD')
                    
                    # Get account info for equity, margin, floating profit
                    account = self.manager.UserAccountGet(user_login)
                    
                    if account is False or account is None:
                        # No positions, equity = balance + credit
                        equity = balance + credit
                        floating_profit = 0.0
                        margin = 0.0
                        margin_free = equity
                        margin_level = 0.0 if margin == 0 else (equity / margin * 100.0)
                    else:
                        # Has positions
                        floating_profit = getattr(account, 'Profit', 0.0)
                        margin = getattr(account, 'Margin', 0.0)
                        margin_free = getattr(account, 'MarginFree', 0.0)
                        margin_level = getattr(account, 'MarginLevel', 0.0)
                        equity = balance + credit + floating_profit
                    
                    result.append(Mt5RealtimeEquity(
                        login=user_login,
                        name=user_name,
                        balance=balance,
                        credit=credit,
                        equity=equity,
                        net_equity=equity - credit,  # Net equity without credit
                        margin=margin,
                        margin_free=margin_free,
                        margin_level=margin_level,
                        floating_profit=floating_profit,
                        group=user_group,
                        currency=currency,
                        timestamp=current_time,
                    ))
                except Exception as e:
                    logger.warning("failed_to_process_user", 
                                 login=user_login if 'user_login' in locals() else None, 
                                 error=str(e))
                    continue
            
            # Only log if not frequently called (commented for WebSocket performance)
            # logger.info("realtime_accounts_fetched", total=len(result))
            return result
        
        return await self._execute_with_retry(_get_realtime)

    async def get_deal_history(
        self,
        login: int | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[Mt5DealHistory]:
        """
        Get deposit, withdrawal, and credit history.
        
        Args:
            login: Specific account login (optional, returns all if not provided)
            from_date: Start date for history
            to_date: End date for history
            
        Returns:
            List of Mt5DealHistory records
        """
        if not self.connected:
            await self.connect()
        
        def _get_deals():
            logger.info("fetching_deal_history", login=login, from_date=from_date, to_date=to_date)
            
            # Convert dates to UTC timestamps (API dates are treated as UTC dates)
            # MT5 Manager API expects UTC timestamps
            if from_date:
                # Create datetime in UTC (treat date as UTC, not local)
                utc_dt = datetime.combine(from_date, datetime.min.time())
                # Calculate timestamp as if this datetime was UTC
                from_ts = int((utc_dt - datetime(1970, 1, 1)).total_seconds())
            else:
                # Default to 30 days ago
                from_ts = int((datetime.now() - timedelta(days=30)).timestamp())
            
            if to_date:
                utc_dt = datetime.combine(to_date, datetime.max.time())
                to_ts = int((utc_dt - datetime(1970, 1, 1)).total_seconds())
            else:
                to_ts = int(datetime.now().timestamp())
            
            logger.info("deal_history_timestamp_range", from_ts=from_ts, to_ts=to_ts)
            
            # Get deals from MT5
            deals = None
            if login is not None:
                # Single account
                logger.info("calling_deal_request", login=login)
                deals = self.manager.DealRequest(login, from_ts, to_ts)
            else:
                # All accounts - use DealRequestByGroup
                logger.info("calling_deal_request_by_group_all")
                deals = self.manager.DealRequestByGroup("*", from_ts, to_ts)
            
            if deals is False:
                error = MT5Manager.LastError()
                logger.error("deal_request_failed", error=error)
                return []
            
            if not deals:
                logger.info("no_deals_found")
                return []
            
            logger.info("deals_received", total=len(deals))
            
            # Filter for balance operations (deposits, withdrawals, credits)
            # Action codes: DEAL_BALANCE = 2, DEAL_CREDIT = 3, DEAL_CHARGE = 4, etc.
            result = []
            for deal in deals:
                try:
                    # Get deal action
                    action_code = deal.Action if hasattr(deal, 'Action') else None
                    
                    # Only include balance operations
                    # Action 2 = Balance (deposit/withdrawal)
                    # Action 3 = Credit
                    # Action 4 = Charge
                    # Action 6 = Correction
                    if action_code not in [2, 3, 4, 6]:
                        continue
                    
                    deal_id = deal.Deal if hasattr(deal, 'Deal') else 0
                    deal_login = deal.Login if hasattr(deal, 'Login') else 0
                    amount = deal.Profit if hasattr(deal, 'Profit') else 0.0
                    comment = deal.Comment if hasattr(deal, 'Comment') else ""
                    timestamp = deal.Time if hasattr(deal, 'Time') else 0
                    
                    # Get balance after deal (if available)
                    balance_after = 0.0
                    if hasattr(deal, 'Storage'):
                        balance_after = deal.Storage
                    
                    # MT5 Manager API returns UTC timestamps but we want to display them as-is
                    # (user sees these times in MT5 and wants to see the same in API)
                    if timestamp:
                        # Use utcfromtimestamp to parse as UTC, display without timezone label
                        utc_time = datetime.utcfromtimestamp(timestamp)
                        datetime_str = utc_time.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        datetime_str = ""
                    
                    # Classify based on comment prefix (case-insensitive)
                    comment_upper = comment.upper() if comment else ""
                    tag = ""
                    action_name = ""
                    
                    # First classify by action code (reliable)
                    action_map = {
                        2: 'DEPOSIT' if amount > 0 else 'WITHDRAWAL',
                        3: 'CREDIT' if amount > 0 else 'CREDIT_OUT',
                        4: 'CHARGE',
                        6: 'CORRECTION',
                    }
                    action_name = action_map.get(action_code, 'UNKNOWN')
                    
                    # Then classify tag by comment prefix
                    if comment_upper.startswith(('DT', 'DT', 'DT', 'DT')):  # dt, Dt, dT, DT
                        tag = "Deposit"
                    elif comment_upper.startswith(('WT', 'WT', 'WT', 'WT')):  # wt, Wt, wT, WT
                        tag = "Withdrawal"
                    elif comment_upper.startswith("REB"):
                        tag = "Rebate"
                    elif comment_upper.startswith("PRO"):
                        tag = "Promotion"
                    else:
                        # Default tag based on action type for untagged deals
                        if action_code == 3:  # CREDIT/CREDIT_OUT actions
                            tag = ""  # Don't tag as promotion, keep empty for credit tracking
                        elif action_code in [2, 4, 6]:  # DEPOSIT/WITHDRAWAL/CHARGE/CORRECTION without prefix
                            tag = "Promotion"
                        else:
                            tag = ""
                    
                    result.append(Mt5DealHistory(
                        deal_id=deal_id,
                        login=deal_login,
                        action=action_name,
                        amount=amount,
                        balance_after=balance_after,
                        comment=comment,
                        timestamp=timestamp,
                        datetime_str=datetime_str,
                        tag=tag,
                    ))
                except Exception as e:
                    logger.warning("failed_to_parse_deal", error=str(e))
                    continue
            
            logger.info("deal_history_fetched", total=len(result))
            return result
        
        return await self._execute_with_retry(_get_deals)

    async def get_trade_deals(
        self,
        login: int | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict]:
        """
        Get trade deals (market orders) with commission, swap, and profit.
        
        Args:
            login: Specific account login (optional)
            from_date: Start date for history
            to_date: End date for history
            
        Returns:
            List of trade deal dicts with commission, swap, profit
        """
        if not self.connected:
            await self.connect()
        
        def _get_trade_deals():
            logger.info("fetching_trade_deals", login=login, from_date=from_date, to_date=to_date)
            
            # Convert dates to timestamps
            if from_date:
                from_ts = int(datetime.combine(from_date, datetime.min.time()).timestamp())
            else:
                from_ts = int((datetime.now() - timedelta(days=30)).timestamp())
            
            if to_date:
                to_ts = int(datetime.combine(to_date, datetime.max.time()).timestamp())
            else:
                to_ts = int(datetime.now().timestamp())
            
            # Get deals from MT5
            deals = None
            if login is not None:
                deals = self.manager.DealRequest(login, from_ts, to_ts)
            else:
                deals = self.manager.DealRequestByGroup("*", from_ts, to_ts)
            
            if deals is False or not deals:
                error = MT5Manager.LastError()
                logger.error("trade_deal_request_failed", error=error)
                return []
            
            logger.info("trade_deals_received", total=len(deals))
            
            # Filter for actual trades (buy/sell operations)
            # Action codes: 0 = BUY, 1 = SELL
            result = []
            for deal in deals:
                try:
                    action_code = deal.Action if hasattr(deal, 'Action') else None
                    
                    # Only include market trades (BUY=0, SELL=1)
                    if action_code not in [0, 1]:
                        continue
                    
                    deal_id = deal.Deal if hasattr(deal, 'Deal') else 0
                    deal_login = deal.Login if hasattr(deal, 'Login') else 0
                    symbol = deal.Symbol if hasattr(deal, 'Symbol') else ""
                    volume = deal.Volume / 10000.0 if hasattr(deal, 'Volume') else 0.0  # Convert from MT5 format
                    profit = deal.Profit if hasattr(deal, 'Profit') else 0.0
                    commission = deal.Commission if hasattr(deal, 'Commission') else 0.0
                    swap = deal.Storage if hasattr(deal, 'Storage') else 0.0
                    timestamp = deal.Time if hasattr(deal, 'Time') else 0
                    price = deal.Price if hasattr(deal, 'Price') else 0.0
                    
                    action_name = 'BUY' if action_code == 0 else 'SELL'
                    
                    # MT5 Manager API returns UTC timestamps but we want to display them as-is
                    # (user sees these times in MT5 and wants to see the same in API)
                    if timestamp:
                        # Use utcfromtimestamp to parse as UTC, display without timezone label
                        utc_time = datetime.utcfromtimestamp(timestamp)
                        datetime_str = utc_time.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        datetime_str = ""
                    
                    result.append({
                        "deal_id": deal_id,
                        "login": deal_login,
                        "symbol": symbol,
                        "action": action_name,
                        "volume": volume,
                        "price": price,
                        "profit": profit,
                        "commission": commission,
                        "swap": swap,
                        "timestamp": timestamp,
                        "datetime": datetime_str,
                    })
                except Exception as e:
                    logger.warning("failed_to_parse_trade_deal", error=str(e))
                    continue
            
            logger.info("trade_deals_filtered", total=len(result))
            return result
        
        return await self._execute_with_retry(_get_trade_deals)

    async def change_group(self, login: int, new_group: str) -> bool:
        """
        Change account group in MT5.
        
        Args:
            login: MT5 account login
            new_group: New group name to move the account to
            
        Returns:
            True if successful
            
        Raises:
            Exception if the operation fails
        """
        if not self.connected:
            await self.connect()
        
        def _change_group():
            # Get current user record
            user = self.manager.UserRequest(login)
            if user is False:
                error = MT5Manager.LastError()
                error_msg = error[2] if error and len(error) > 2 else "User not found"
                raise Exception(f"Failed to get user {login}: {error_msg}")
            
            # Update group
            user.Group = new_group
            
            # Apply update
            result = self.manager.UserUpdate(user)
            if result is False:
                error = MT5Manager.LastError()
                error_msg = error[2] if error and len(error) > 2 else "Unknown error"
                raise Exception(f"Failed to change group: {error_msg}")
            
            logger.info("group_changed", login=login, new_group=new_group)
            return True
        
        return await self._execute_with_retry(_change_group)

    async def change_password(self, login: int, new_password: str) -> bool:
        """
        Change main trading password for MT5 account.
        
        Args:
            login: MT5 account login
            new_password: New main password
            
        Returns:
            True if successful
            
        Raises:
            Exception if the operation fails
        """
        if not self.connected:
            await self.connect()
        
        def _change_password():
            # PasswordChange(login, password_type, new_password)
            # password_type: 0 = main password, 1 = investor password
            result = self.manager.PasswordChange(login, 0, new_password)
            if result is False:
                error = MT5Manager.LastError()
                error_msg = error[2] if error and len(error) > 2 else "Unknown error"
                raise Exception(f"Failed to change password: {error_msg}")
            
            logger.info("password_changed", login=login)
            return True
        
        return await self._execute_with_retry(_change_password)

    async def change_investor_password(self, login: int, new_password: str) -> bool:
        """
        Change investor (read-only) password for MT5 account.
        
        Args:
            login: MT5 account login
            new_password: New investor password
            
        Returns:
            True if successful
            
        Raises:
            Exception if the operation fails
        """
        if not self.connected:
            await self.connect()
        
        def _change_investor_password():
            # PasswordChange(login, password_type, new_password)
            # password_type: 0 = main password, 1 = investor password
            result = self.manager.PasswordChange(login, 1, new_password)
            if result is False:
                error = MT5Manager.LastError()
                error_msg = error[2] if error and len(error) > 2 else "Unknown error"
                raise Exception(f"Failed to change investor password: {error_msg}")
            
            logger.info("investor_password_changed", login=login)
            return True
        
        return await self._execute_with_retry(_change_investor_password)

    async def health_check(self) -> dict[str, Any]:
        try:
            if not self.connected:
                await self.connect()
            def _ping():
                users = self.manager.UserGetByGroup("*")
                return users is not False
            healthy = await asyncio.get_event_loop().run_in_executor(None, _ping)
            return {"status": "healthy" if healthy else "unhealthy", "connected": self.connected, "host": settings.mt5_manager_host, "port": settings.mt5_manager_port, "circuit_breaker": self.circuit_breaker.state, "mode": "production", "package": "MT5Manager"}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "connected": False}

_mt5_service: MT5ManagerService | None = None

def get_mt5_service() -> MT5ManagerService:
    global _mt5_service
    if _mt5_service is None:
        _mt5_service = MT5ManagerService()
    return _mt5_service
