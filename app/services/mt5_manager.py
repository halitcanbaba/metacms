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
    margin_free: float
    margin_level: float
    status: str

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
    floating_profit: float
    group: str
    currency: str
    timestamp: int  # Unix timestamp of the report

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

@dataclass
class NetPositionSummary:
    symbol: str
    buy_volume: float
    sell_volume: float
    net_volume: float
    positions_count: int

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
            
            # MTUser doesn't have MarginFree/MarginLevel - use defaults for new account
            # These values are only available via UserAccountGet after trading starts
            return Mt5AccountInfo(
                login=user.Login, 
                group=user.Group, 
                leverage=user.Leverage, 
                currency=currency,
                balance=user.Balance, 
                credit=user.Credit, 
                margin_free=0.0,  # New account has no margin usage
                margin_level=0.0,  # New account has no margin level
                status="active"
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
                        symbol_data[symbol] = {"buy_volume": 0.0, "sell_volume": 0.0, "count": 0}
                    
                    # Get volume in lots (MT5 stores in 10000ths)
                    volume_lots = pos.Volume / 10000.0
                    
                    # Aggregate by action (buy/sell)
                    if pos.Action == MT5Manager.MTPosition.EnPositionAction.POSITION_BUY:
                        symbol_data[symbol]["buy_volume"] += volume_lots
                    else:  # POSITION_SELL
                        symbol_data[symbol]["sell_volume"] += volume_lots
                    
                    symbol_data[symbol]["count"] += 1
                    
                    logger.debug("position_processed", 
                                login=pos.Login,
                                symbol=symbol, 
                                action="buy" if pos.Action == MT5Manager.MTPosition.EnPositionAction.POSITION_BUY else "sell",
                                volume=volume_lots)
                    
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
                    positions_count=data["count"]
                )
                for sym, data in symbol_data.items()
            ]
            
            logger.info("positions_aggregated", total_symbols=len(result), total_positions=sum(p.positions_count for p in result))
            
            return result
        return await self._execute_with_retry(_get_positions)

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
            
            logger.info("positions_retrieved_by_login", 
                       login=login, 
                       symbol=symbol_filter,
                       count=len(result))
            
            return result
        
        return await self._execute_with_retry(_get_positions)

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
            
            return Mt5AccountInfo(
                login=user.Login, 
                group=user.Group, 
                leverage=user.Leverage, 
                currency="USD",
                balance=user.Balance, 
                credit=user.Credit, 
                margin_free=margin_free,
                margin_level=margin_level, 
                status="active"
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
            # Convert dates to Unix timestamps (start of day)
            if from_date:
                from_timestamp = int(datetime.combine(from_date, datetime.min.time()).timestamp())
            else:
                # Default to yesterday
                yesterday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                from_timestamp = int((yesterday - timedelta(days=1)).timestamp())
            
            if to_date:
                # End of day
                to_timestamp = int(datetime.combine(to_date, datetime.max.time()).timestamp())
            else:
                # Default to today
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
                    
                    report_date = datetime.fromtimestamp(date_value).strftime('%Y-%m-%d')
                    
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
                        floating_profit=floating_profit,
                        group=report.Group if hasattr(report, 'Group') else "",
                        currency=report.Currency if hasattr(report, 'Currency') else "USD",
                        timestamp=date_value,  # Use the date_value we already extracted
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
            logger.info("fetching_realtime_accounts", login=login, group=group)
            
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
            
            logger.info("processing_users", total=len(users))
            
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
            
            logger.info("realtime_accounts_fetched", total=len(result))
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
            
            # Convert dates to timestamps
            if from_date:
                from_ts = int(datetime.combine(from_date, datetime.min.time()).timestamp())
            else:
                # Default to 30 days ago
                from_ts = int((datetime.now() - timedelta(days=30)).timestamp())
            
            if to_date:
                to_ts = int(datetime.combine(to_date, datetime.max.time()).timestamp())
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
                    
                    # Map action codes to readable names
                    action_map = {
                        2: 'DEPOSIT' if deal.Profit > 0 else 'WITHDRAWAL',
                        3: 'CREDIT' if deal.Profit > 0 else 'CREDIT_OUT',
                        4: 'CHARGE',
                        6: 'CORRECTION',
                    }
                    action_name = action_map.get(action_code, 'UNKNOWN')
                    
                    deal_id = deal.Deal if hasattr(deal, 'Deal') else 0
                    deal_login = deal.Login if hasattr(deal, 'Login') else 0
                    amount = deal.Profit if hasattr(deal, 'Profit') else 0.0
                    comment = deal.Comment if hasattr(deal, 'Comment') else ""
                    timestamp = deal.Time if hasattr(deal, 'Time') else 0
                    
                    # Get balance after deal (if available)
                    balance_after = 0.0
                    if hasattr(deal, 'Storage'):
                        balance_after = deal.Storage
                    
                    datetime_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S') if timestamp else ""
                    
                    result.append(Mt5DealHistory(
                        deal_id=deal_id,
                        login=deal_login,
                        action=action_name,
                        amount=amount,
                        balance_after=balance_after,
                        comment=comment,
                        timestamp=timestamp,
                        datetime_str=datetime_str,
                    ))
                except Exception as e:
                    logger.warning("failed_to_parse_deal", error=str(e))
                    continue
            
            logger.info("deal_history_fetched", total=len(result))
            return result
        
        return await self._execute_with_retry(_get_deals)

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
