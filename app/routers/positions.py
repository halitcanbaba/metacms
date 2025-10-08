"""
Positions monitoring router.

Provides endpoints for real-time position monitoring and analysis.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.deps import get_current_user_id, get_positions_service, get_mt5_manager
from app.services.positions import PositionsService
from app.services.mt5_manager import MT5ManagerService
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/positions",
    tags=["Positions"],
)


@router.get("/net")
async def get_net_positions(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    current_user_id: int = Depends(get_current_user_id),
    positions_service: PositionsService = Depends(get_positions_service),
):
    """Get net positions summary by symbol."""
    try:
        # Service returns dict with net_positions list and totals
        result = await positions_service.get_net_positions(symbol_filter=symbol)
        return result
    except Exception as e:
        logger.error("failed_to_get_net_positions", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get net positions")


@router.get("/open")
async def get_open_positions(
    login: Optional[int] = Query(None, description="Filter by MT5 login"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    current_user_id: int = Depends(get_current_user_id),
    positions_service: PositionsService = Depends(get_positions_service),
):
    """Get open positions."""
    try:
        positions = await positions_service.get_open_positions(login=login, symbol=symbol)
        return {
            "positions": positions,
            "total": len(positions),
        }
    except Exception as e:
        logger.error("failed_to_get_open_positions", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get open positions")


@router.get("/exposure")
async def get_exposure_summary(
    current_user_id: int = Depends(get_current_user_id),
    positions_service: PositionsService = Depends(get_positions_service),
):
    """Get exposure summary."""
    try:
        exposure = await positions_service.get_exposure_summary()
        return exposure
    except Exception as e:
        logger.error("failed_to_get_exposure", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get exposure summary")


@router.get("/symbol/{symbol}")
async def get_symbol_statistics(
    symbol: str,
    current_user_id: int = Depends(get_current_user_id),
    positions_service: PositionsService = Depends(get_positions_service),
):
    """Get statistics for a specific symbol."""
    try:
        stats = await positions_service.get_symbol_statistics(symbol)
        if not stats:
            raise HTTPException(status_code=404, detail="Symbol not found")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_get_symbol_stats", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get symbol statistics")


@router.get("/account/{login}")
async def get_account_positions(
    login: int,
    current_user_id: int = Depends(get_current_user_id),
    mt5: MT5ManagerService = Depends(get_mt5_manager),
):
    """Get all positions for a specific account."""
    try:
        # Get account info
        account_info = await mt5.get_account_info(login)
        
        # Get positions (placeholder - would need actual MT5 API call)
        return {
            "login": login,
            "account_info": {
                "balance": account_info.balance,
                "credit": account_info.credit,
                "margin_free": account_info.margin_free,
                "margin_level": account_info.margin_level,
            },
            "positions": [],  # Would be populated from MT5 API
        }
    except Exception as e:
        logger.error("failed_to_get_account_positions", login=login, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get account positions")
