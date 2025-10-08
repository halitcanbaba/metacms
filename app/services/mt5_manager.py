"""MetaTrader 5 Manager API service using official MT5Manager Python package."""
import asyncio
import time
from dataclasses import dataclass
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

    async def create_account(self, group: str, leverage: int, currency: str, password: str, name: str = "", first_name: str = "", last_name: str = "") -> Mt5AccountInfo:
        def _create():
            # Find the highest existing login number by getting all users in the group
            max_login = 0
            try:
                # Get all users from the group to find the highest login
                users = self.manager.UserGetByGroup(group)
                if users and len(users) > 0:
                    max_login = max(u.Login for u in users)
                    logger.info("found_max_login", group=group, max_login=max_login, total_users=len(users))
                else:
                    logger.info("no_existing_users", group=group)
            except Exception as e:
                logger.warning("could_not_get_max_login", error=str(e), group=group)
            
            # Create new user with next available login
            user = MT5Manager.MTUser(self.manager)
            if max_login > 0:
                user.Login = max_login + 1  # Set next login number
            user.Group = group
            user.Leverage = leverage
            user.FirstName = first_name or name.split()[0] if name else "User"
            user.LastName = last_name or (name.split()[1] if len(name.split()) > 1 else "Account")
            
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
                raise MT5Exception(f"Account creation failed: {error[2]}", error[1].value)
            
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

    async def apply_balance_operation(self, login: int, op_type: str, amount: float, comment: str = "") -> Mt5BalanceResult:
        def _apply():
            if op_type in ("deposit", "withdrawal"):
                deal_action = MT5Manager.MTDeal.EnDealAction.DEAL_BALANCE
            elif op_type in ("credit_in", "credit_out"):
                deal_action = MT5Manager.MTDeal.EnDealAction.DEAL_CREDIT
            else:
                raise MT5InvalidDataError(f"Invalid operation type: {op_type}")
            deal_id = self.manager.DealerBalance(login, amount, deal_action, comment)
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
