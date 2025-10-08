"""Health check router."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.domain.dto import HealthResponse
from app.services.mt5_manager import get_mt5_service
from app.services.pipedrive import PipedriveClient

router = APIRouter()


@router.get("", response_model=HealthResponse)
async def health_check():
    """Overall health check."""
    return HealthResponse(status="healthy", timestamp=datetime.now(timezone.utc))


@router.get("/database", response_model=HealthResponse)
async def database_health(db: AsyncSession = Depends(get_db)):
    """Database health check."""
    try:
        # Simple query to check database connectivity
        await db.execute("SELECT 1")
        return HealthResponse(
            status="healthy", timestamp=datetime.now(timezone.utc), database="connected"
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy", timestamp=datetime.now(timezone.utc), database=f"error: {str(e)}"
        )


@router.get("/mt5", response_model=HealthResponse)
async def mt5_health():
    """MT5 Manager API health check."""
    try:
        mt5_service = get_mt5_service()
        health = await mt5_service.health_check()
        return HealthResponse(
            status=health.get("status", "unknown"), timestamp=datetime.now(timezone.utc), mt5=str(health)
        )
    except Exception as e:
        return HealthResponse(status="unhealthy", timestamp=datetime.now(timezone.utc), mt5=f"error: {str(e)}")


@router.get("/pipedrive", response_model=HealthResponse)
async def pipedrive_health(db: AsyncSession = Depends(get_db)):
    """Pipedrive API health check."""
    try:
        client = PipedriveClient(db)
        health = await client.health_check()
        return HealthResponse(
            status=health.get("status", "unknown"), timestamp=datetime.now(timezone.utc), pipedrive=str(health)
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy", timestamp=datetime.now(timezone.utc), pipedrive=f"error: {str(e)}"
        )
