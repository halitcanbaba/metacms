"""
WebSocket router for real-time data streaming.
"""
import asyncio
import structlog
from typing import Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_mt5_manager
from app.services.mt5_manager import MT5ManagerService
from app.repositories.accounts_repo import AccountsRepository

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/ws", tags=["WebSocket"])

# Connection manager to track active WebSocket connections per login
active_connections: Dict[int, WebSocket] = {}

# Connection manager for dashboard WebSocket connections
dashboard_connections: Dict[str, WebSocket] = {}


@router.websocket("/account/{login}")
async def account_realtime(
    websocket: WebSocket,
    login: int,
    db: AsyncSession = Depends(get_db),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
):
    """
    WebSocket endpoint for real-time account data.
    
    Streams account data every 500ms:
    - Realtime equity, margin, floating P/L
    - Open positions with current profit
    - Account balance and credit
    
    Only one connection per login is allowed. If a new connection is made,
    the old one is automatically closed.
    """
    # Check if there's already an active connection for this login
    if login in active_connections:
        old_ws = active_connections[login]
        try:
            logger.info("closing_old_websocket_connection", login=login)
            await old_ws.close(code=1000, reason="New connection established")
        except:
            pass
    
    await websocket.accept()
    active_connections[login] = websocket
    logger.info("websocket_connected", login=login, total_connections=len(active_connections))
    
    # Verify account exists
    repo = AccountsRepository(db)
    account = await repo.get_by_login(login)
    if not account:
        await websocket.send_json({"error": "Account not found"})
        await websocket.close()
        if login in active_connections:
            del active_connections[login]
        return
    
    try:
        while True:
            try:
                # Fetch realtime data
                realtime_data = await mt5.get_realtime_accounts(login=login)
                
                # Fetch open positions
                positions = await mt5.get_positions_by_login(login=login)
                
                # Prepare response
                response = {
                    "type": "account_update",
                    "login": login,
                    "realtime": None,
                    "positions": [],
                }
                
                # Add realtime data
                if realtime_data and len(realtime_data) > 0:
                    rt = realtime_data[0]
                    response["realtime"] = {
                        "balance": rt.balance,
                        "credit": rt.credit,
                        "equity": rt.equity,
                        "net_equity": rt.net_equity,
                        "margin": rt.margin,
                        "margin_free": rt.margin_free,
                        "margin_level": rt.margin_level,
                        "floating_profit": rt.floating_profit,
                    }
                
                # Add positions
                for pos in positions:
                    response["positions"].append({
                        "ticket": pos.get("ticket"),
                        "symbol": pos.get("symbol"),
                        "type": pos.get("action"),  # 0=buy, 1=sell
                        "volume": pos.get("volume"),
                        "price_open": pos.get("price_open"),
                        "price_current": pos.get("price_current"),
                        "profit": pos.get("profit"),
                        "swap": pos.get("swap"),
                        "commission": pos.get("commission"),
                    })
                
                # Send data
                await websocket.send_json(response)
                
                # Wait 500ms before next update
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error("websocket_data_fetch_error", login=login, error=str(e))
                await websocket.send_json({"error": f"Failed to fetch data: {str(e)}"})
                await asyncio.sleep(0.5)
                
    except WebSocketDisconnect:
        logger.info("websocket_disconnected", login=login)
    except Exception as e:
        logger.error("websocket_error", login=login, error=str(e))
        try:
            await websocket.close()
        except:
            pass
    finally:
        # Clean up connection from active connections
        if login in active_connections and active_connections[login] == websocket:
            del active_connections[login]
            logger.info("websocket_cleaned_up", login=login, remaining_connections=len(active_connections))


@router.websocket("/dashboard")
async def dashboard_realtime(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
):
    """
    WebSocket endpoint for real-time dashboard data.
    
    Streams aggregated data every 500ms:
    - All accounts' realtime data
    - All open positions
    - Margin call alerts
    """
    import uuid
    connection_id = str(uuid.uuid4())
    
    # Check if there's already an active connection (optional: allow multiple dashboard connections)
    # For now, we'll track them but allow multiple
    await websocket.accept()
    dashboard_connections[connection_id] = websocket
    logger.info("dashboard_websocket_connected", total_connections=len(dashboard_connections))
    
    try:
        while True:
            try:
                # Fetch all accounts' realtime data
                realtime_data = await mt5.get_realtime_accounts()
                
                # Fetch all open positions
                all_positions = await mt5.get_all_positions()
                
                # Calculate statistics
                total_equity = 0.0
                total_balance = 0.0
                total_margin = 0.0
                total_floating_profit = 0.0
                margin_call_list = []
                
                for rt in realtime_data:
                    # Aggregate stats
                    equity = float(rt.equity) if rt.equity else 0.0
                    balance = float(rt.balance) if rt.balance else 0.0
                    margin = float(rt.margin) if rt.margin else 0.0
                    floating = float(rt.floating_profit) if rt.floating_profit else 0.0
                    
                    total_equity += equity
                    total_balance += balance
                    total_margin += margin
                    total_floating_profit += floating
                    
                    # Check for margin call (margin level < 100%)
                    if margin > 0:
                        margin_level = (equity / margin) * 100
                        if margin_level < 100:
                            margin_call_list.append({
                                "login": rt.login,
                                "name": f"Account {rt.login}",  # Simple name without DB query
                                "equity": equity,
                                "margin": margin,
                                "margin_level": margin_level,
                                "margin_free": float(rt.margin_free) if rt.margin_free else 0.0
                            })
                
                # Sort margin calls by level (most critical first)
                margin_call_list.sort(key=lambda x: x["margin_level"])
                
                # Count positions
                active_positions = len(all_positions)
                
                # Calculate total volume from positions
                total_volume = sum(pos.get("volume", 0.0) for pos in all_positions)
                
                # Prepare response
                response = {
                    "type": "dashboard_update",
                    "timestamp": asyncio.get_event_loop().time(),
                    "stats": {
                        "total_equity": total_equity,
                        "total_balance": total_balance,
                        "total_margin": total_margin,
                        "total_floating_profit": total_floating_profit,
                        "active_positions": active_positions,
                        "total_volume": total_volume,
                    },
                    "margin_calls": margin_call_list[:10],  # Top 10 most critical
                    "positions": all_positions[:50],  # Limit to 50 most recent positions
                }
                
                # Send data
                await websocket.send_json(response)
                
                # Wait 500ms before next update
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error("dashboard_ws_error", error=str(e))
                await websocket.send_json({"error": f"Failed to fetch data: {str(e)}"})
                await asyncio.sleep(0.5)
                
    except WebSocketDisconnect:
        logger.info("dashboard_ws_disconnected")
    except Exception as e:
        logger.error("dashboard_ws_error", error=str(e))
        try:
            await websocket.close()
        except:
            pass
    finally:
        # Clean up connection
        if connection_id in dashboard_connections:
            del dashboard_connections[connection_id]
            logger.info("dashboard_ws_cleaned_up", remaining=len(dashboard_connections))
