"""Positions aggregation and monitoring service."""
from collections import defaultdict
from typing import Any

import structlog

from app.services.mt5_manager import MT5ManagerService, get_mt5_service

logger = structlog.get_logger()


class PositionsService:
    """Service for aggregating and monitoring trading positions."""

    def __init__(self, mt5_service: MT5ManagerService | None = None):
        self.mt5_service = mt5_service or get_mt5_service()

    async def get_net_positions(self, symbol_filter: str | None = None) -> dict[str, Any]:
        """
        Get net positions aggregated by symbol.
        
        Args:
            symbol_filter: Optional symbol filter (e.g., "EUR*" for all EUR pairs)
            
        Returns:
            Dict with aggregated position data by symbol
        """
        try:
            # Get net positions from MT5 (already aggregated by symbol)
            mt5_positions = await self.mt5_service.get_net_positions(symbol_filter)

            # Calculate totals
            total_volume = 0.0
            total_profit = 0.0
            total_positions = 0

            # Convert to dict format for response
            net_positions = []
            for pos in mt5_positions:
                net_positions.append({
                    "symbol": pos.symbol,
                    "buy_volume": pos.buy_volume,
                    "sell_volume": pos.sell_volume,
                    "net_volume": pos.net_volume,
                    "net_profit": 0.0,  # Would need to calculate from position data
                    "positions_count": pos.positions_count,
                })
                total_volume += abs(pos.net_volume)
                total_positions += pos.positions_count

            # Sort by absolute net volume descending
            net_positions.sort(key=lambda x: abs(x["net_volume"]), reverse=True)

            logger.info("net_positions_aggregated", total_positions=total_positions, symbols_count=len(net_positions))

            return {
                "total_positions": total_positions,
                "total_volume": total_volume,
                "total_profit": total_profit,
                "net_positions": net_positions,
            }

        except Exception as e:
            logger.error("get_net_positions_failed", error=str(e))
            raise

    async def get_open_positions(self, login: int | None = None, symbol: str | None = None) -> list[dict[str, Any]]:
        """
        Get open positions for a specific login or all logins.
        
        Args:
            login: Optional MT5 login to filter positions
            symbol: Optional symbol to filter positions
            
        Returns:
            List of open positions
        """
        try:
            logger.info("get_open_positions", login=login, symbol=symbol)
            
            # Get positions from MT5
            mt5_positions = await self.mt5_service.get_positions_by_login(login, symbol)
            
            # Convert to dict format
            positions = []
            for pos in mt5_positions:
                positions.append({
                    "ticket": pos.get("ticket", 0),
                    "login": pos.get("login", 0),
                    "symbol": pos.get("symbol", ""),
                    "volume": pos.get("volume", 0.0),
                    "action": pos.get("action", 0),  # 0=buy, 1=sell
                    "type": "buy" if pos.get("action", 0) == 0 else "sell",
                    "price_open": pos.get("price_open", 0.0),
                    "price_current": pos.get("price_current", 0.0),
                    "profit": pos.get("profit", 0.0),
                    "swap": pos.get("swap", 0.0),
                    "commission": pos.get("commission", 0.0),
                    "time_create": pos.get("time_create", 0),
                })
            
            logger.info("positions_retrieved", count=len(positions), login=login, symbol=symbol)
            return positions

        except Exception as e:
            logger.error("get_open_positions_failed", error=str(e), login=login)
            raise

    async def get_exposure_summary(self) -> dict[str, Any]:
        """
        Get overall market exposure summary.
        
        Returns:
            Dict with exposure metrics
        """
        try:
            net_positions_data = await self.get_net_positions()

            # Calculate risk metrics
            total_long_volume = sum(p["buy_volume"] for p in net_positions_data["net_positions"])
            total_short_volume = sum(p["sell_volume"] for p in net_positions_data["net_positions"])

            # Identify largest exposures
            largest_exposures = net_positions_data["net_positions"][:10]  # Top 10

            logger.info("exposure_summary_calculated")

            return {
                "total_long_volume": total_long_volume,
                "total_short_volume": total_short_volume,
                "net_exposure": total_long_volume - total_short_volume,
                "total_profit": net_positions_data["total_profit"],
                "positions_count": net_positions_data["total_positions"],
                "largest_exposures": largest_exposures,
            }

        except Exception as e:
            logger.error("get_exposure_summary_failed", error=str(e))
            raise

    async def get_symbol_statistics(self, symbol: str) -> dict[str, Any]:
        """
        Get statistics for a specific symbol.
        
        Args:
            symbol: Trading symbol (e.g., "EURUSD")
            
        Returns:
            Dict with symbol statistics
        """
        try:
            # Get positions for this symbol
            all_positions = await self.get_net_positions(symbol_filter=symbol)

            symbol_data = next(
                (p for p in all_positions["net_positions"] if p["symbol"] == symbol),
                None,
            )

            if not symbol_data:
                return {
                    "symbol": symbol,
                    "buy_volume": 0.0,
                    "sell_volume": 0.0,
                    "net_volume": 0.0,
                    "net_profit": 0.0,
                    "positions_count": 0,
                }

            logger.info("symbol_statistics_retrieved", symbol=symbol)
            return symbol_data

        except Exception as e:
            logger.error("get_symbol_statistics_failed", error=str(e), symbol=symbol)
            raise
