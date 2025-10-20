"""
Agent management router.

Provides CRUD operations for agents (sales/support agents).
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user_id, require_role, get_audit_service
from app.domain.dto import (
    AgentCreate,
    AgentUpdate,
    AgentResponse,
    PaginatedResponse,
)
from app.domain.enums import UserRole
from app.repositories.agents_repo import AgentsRepository
from app.services.audit import AuditService
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/agents",
    tags=["agents"],
)


@router.get(
    "",
    response_model=PaginatedResponse[AgentResponse],
    summary="List agents",
    description="Get paginated list of agents with optional search",
)
async def list_agents(
    search: Optional[str] = Query(None, description="Search by name, email, or phone"),
    active_only: bool = Query(False, description="Show only active agents"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Number of records to return"),
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
) -> PaginatedResponse[AgentResponse]:
    """
    List agents with optional search and pagination.
    
    - Supports search across name, email, and phone fields
    - Can filter by active status
    - Returns paginated results
    - Requires authentication
    """
    repo = AgentsRepository(db)
    
    if search:
        items, total = await repo.search(search, skip=skip, limit=limit)
    else:
        items, total = await repo.list_all(skip=skip, limit=limit, active_only=active_only)
    
    return PaginatedResponse(
        items=[AgentResponse.model_validate(item) for item in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post(
    "",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create agent",
    description="Create a new agent",
)
async def create_agent(
    agent_data: AgentCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(UserRole.ADMIN)),
    audit: AuditService = Depends(get_audit_service),
) -> AgentResponse:
    """
    Create a new agent.
    
    - Requires ADMIN role
    - Records audit log
    """
    repo = AgentsRepository(db)
    
    # Check if agent with same email already exists
    existing = await repo.get_by_email(agent_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent with email {agent_data.email} already exists",
        )
    
    # Create agent in database
    agent = await repo.create(
        name=agent_data.name,
        email=agent_data.email,
        phone=agent_data.phone,
    )
    
    await db.commit()
    
    # Log audit
    await audit.log(
        actor_id=current_user.id,
        action="create",
        entity="agent",
        entity_id=str(agent.id),
        after={"name": agent.name, "email": agent.email},
    )
    
    logger.info("agent_created", agent_id=agent.id, name=agent.name)
    
    return AgentResponse.model_validate(agent)


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Get agent",
    description="Get agent details by ID",
)
async def get_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    current_user_id: int = Depends(get_current_user_id),
) -> AgentResponse:
    """
    Get agent by ID.
    
    - Returns agent details
    - Requires authentication
    """
    repo = AgentsRepository(db)
    agent = await repo.get_by_id(agent_id)
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found",
        )
    
    return AgentResponse.model_validate(agent)


@router.patch(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="Update agent",
    description="Update agent details",
)
async def update_agent(
    agent_id: int,
    agent_data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(UserRole.ADMIN)),
    audit: AuditService = Depends(get_audit_service),
) -> AgentResponse:
    """
    Update an existing agent.
    
    - Requires ADMIN role
    - Records audit log
    """
    repo = AgentsRepository(db)
    
    # Get existing agent
    agent = await repo.get_by_id(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found",
        )
    
    # If email is changing, check for conflicts
    if agent_data.email and agent_data.email != agent.email:
        existing = await repo.get_by_email(agent_data.email)
        if existing and existing.id != agent_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Agent with email {agent_data.email} already exists",
            )
    
    # Track changes for audit
    before_data = {}
    after_data = {}
    for field, new_value in agent_data.model_dump(exclude_unset=True).items():
        old_value = getattr(agent, field)
        if old_value != new_value:
            before_data[field] = old_value
            after_data[field] = new_value
            # Update the agent object
            setattr(agent, field, new_value)
    
    # Update in database
    updated_agent = await repo.update(agent)
    await db.commit()
    
    # Log audit
    if before_data:
        await audit.log(
            actor_id=current_user.id,
            action="update",
            entity="agent",
            entity_id=str(agent_id),
            before=before_data,
            after=after_data,
        )
    
    logger.info("agent_updated", agent_id=agent_id, changes=after_data)
    
    return AgentResponse.model_validate(updated_agent)


@router.delete(
    "/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete agent",
    description="Delete an agent",
)
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(UserRole.ADMIN)),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    """
    Delete an agent.
    
    - Requires ADMIN role
    - Records audit log
    - Note: This will fail if agent has associated customers (foreign key constraint)
    """
    repo = AgentsRepository(db)
    
    # Get existing agent
    agent = await repo.get_by_id(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent with ID {agent_id} not found",
        )
    
    # Delete agent
    try:
        await repo.delete(agent)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error("agent_delete_failed", agent_id=agent_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete agent with associated customers. Please reassign customers first.",
        )
    
    # Log audit
    await audit.log(
        actor_id=current_user.id,
        action="delete",
        entity="agent",
        entity_id=str(agent_id),
        before={"name": agent.name, "email": agent.email},
    )
    
    logger.info("agent_deleted", agent_id=agent_id)
