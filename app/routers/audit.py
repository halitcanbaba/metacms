"""
Audit log router.

Provides endpoints for querying audit logs.
"""
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user_id, require_role
from app.domain.dto import AuditLogResponse, PaginatedResponse
from app.domain.enums import AuditAction, UserRole
from app.repositories.audit_repo import AuditRepository
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/audit",
    tags=["audit"],
)


@router.get(
    "",
    response_model=PaginatedResponse[AuditLogResponse],
    summary="List audit logs",
    description="Get paginated list of audit logs with optional filters",
)
async def list_audit_logs(
    action: Optional[AuditAction] = Query(None, description="Filter by action"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    actor_id: Optional[int] = Query(None, description="Filter by actor ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Number of records to return"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(require_role(UserRole.SUPPORT)),
) -> PaginatedResponse[AuditLogResponse]:
    """
    List audit logs with optional filters.
    
    - Supports filtering by action, entity, actor, and date range
    - Returns paginated results
    - Requires SUPPORT role or higher
    """
    repo = AuditRepository(db)
    
    items, total = await repo.list_all(
        skip=skip,
        limit=limit,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    return PaginatedResponse(
        items=[AuditLogResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/search",
    response_model=list[AuditLogResponse],
    summary="Search audit logs",
    description="Search audit logs by query string",
)
async def search_audit_logs(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(100, ge=1, le=500, description="Number of records to return"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(require_role(UserRole.SUPPORT)),
) -> list[AuditLogResponse]:
    """
    Search audit logs.
    
    - Searches across entity types, IDs, and details
    - Returns matching results
    - Requires SUPPORT role or higher
    """
    repo = AuditRepository(db)
    
    results = await repo.search(query, limit=limit)
    
    return [AuditLogResponse.model_validate(item) for item in results]


@router.get(
    "/recent",
    response_model=list[AuditLogResponse],
    summary="Get recent audit logs",
    description="Get most recent audit logs",
)
async def get_recent_audit_logs(
    limit: int = Query(50, ge=1, le=200, description="Number of records to return"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(require_role(UserRole.SUPPORT)),
) -> list[AuditLogResponse]:
    """
    Get most recent audit logs.
    
    - Returns latest audit entries
    - Ordered by creation time (newest first)
    - Requires SUPPORT role or higher
    """
    repo = AuditRepository(db)
    
    logs = await repo.get_recent(limit=limit)
    
    return [AuditLogResponse.model_validate(log) for log in logs]


@router.get(
    "/entity/{entity_type}/{entity_id}",
    response_model=list[AuditLogResponse],
    summary="Get entity audit trail",
    description="Get complete audit trail for a specific entity",
)
async def get_entity_audit_trail(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(require_role(UserRole.SUPPORT)),
) -> list[AuditLogResponse]:
    """
    Get audit trail for a specific entity.
    
    - Returns all audit logs for the entity
    - Ordered chronologically
    - Requires SUPPORT role or higher
    """
    repo = AuditRepository(db)
    
    logs = await repo.get_by_entity(entity_type=entity_type, entity_id=entity_id)
    
    if not logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit logs found for {entity_type}:{entity_id}",
        )
    
    return [AuditLogResponse.model_validate(log) for log in logs]


@router.get(
    "/actor/{actor_id}",
    response_model=list[AuditLogResponse],
    summary="Get actor audit logs",
    description="Get all audit logs for a specific actor (user)",
)
async def get_actor_audit_logs(
    actor_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Number of records to return"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(require_role(UserRole.SUPPORT)),
) -> list[AuditLogResponse]:
    """
    Get audit logs for a specific actor.
    
    - Returns all actions performed by the user
    - Supports pagination
    - Requires SUPPORT role or higher
    """
    repo = AuditRepository(db)
    
    logs = await repo.get_by_actor(actor_id=actor_id, skip=skip, limit=limit)
    
    return [AuditLogResponse.model_validate(log) for log in logs]


@router.get(
    "/request/{request_id}",
    response_model=list[AuditLogResponse],
    summary="Get request audit logs",
    description="Get all audit logs for a specific request ID",
)
async def get_request_audit_logs(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(require_role(UserRole.SUPPORT)),
) -> list[AuditLogResponse]:
    """
    Get audit logs for a specific request.
    
    - Returns all audit logs from a single request
    - Useful for debugging and tracing
    - Requires SUPPORT role or higher
    """
    repo = AuditRepository(db)
    
    logs = await repo.get_by_request_id(request_id=request_id)
    
    if not logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit logs found for request ID: {request_id}",
        )
    
    return [AuditLogResponse.model_validate(log) for log in logs]


@router.get(
    "/statistics",
    summary="Get audit statistics",
    description="Get audit log statistics",
)
async def get_audit_statistics(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(require_role(UserRole.ADMIN)),
):
    """
    Get audit statistics.
    
    - Action counts by type
    - User activity summary
    - Temporal analysis
    - Requires ADMIN role
    """
    repo = AuditRepository(db)
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get action counts
    action_counts = await repo.count_by_action(
        start_date=start_date,
        end_date=end_date,
    )
    
    # Get recent logs for additional stats
    recent_logs = await repo.get_recent(limit=1000)
    
    # Calculate user activity
    user_activity = {}
    for log in recent_logs:
        if log.actor_id:
            user_activity[log.actor_id] = user_activity.get(log.actor_id, 0) + 1
    
    # Calculate entity type distribution
    entity_types = {}
    for log in recent_logs:
        if log.entity_type:
            entity_types[log.entity_type] = entity_types.get(log.entity_type, 0) + 1
    
    return {
        "period_days": days,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "action_counts": action_counts,
        "user_activity": user_activity,
        "entity_types": entity_types,
        "total_logs": len(recent_logs),
    }
