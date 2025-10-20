"""Agents repository for database operations."""
from typing import Any
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Agent


class AgentsRepository:
    """Repository for Agent model operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, agent_id: int) -> Agent | None:
        """Get agent by ID."""
        result = await self.db.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Agent | None:
        """Get agent by email."""
        result = await self.db.execute(
            select(Agent).where(Agent.email == email)
        )
        return result.scalar_one_or_none()

    async def search(self, search_term: str, skip: int = 0, limit: int = 20) -> tuple[list[Agent], int]:
        """
        Search agents by name, email, or phone.
        
        Returns:
            Tuple of (agents list, total count)
        """
        # Build search filter
        search_filter = or_(
            Agent.name.ilike(f"%{search_term}%"),
            Agent.email.ilike(f"%{search_term}%"),
            Agent.phone.ilike(f"%{search_term}%"),
        )

        # Get total count
        count_result = await self.db.execute(
            select(func.count()).select_from(Agent).where(search_filter)
        )
        total = count_result.scalar_one()

        # Get agents
        result = await self.db.execute(
            select(Agent)
            .where(search_filter)
            .offset(skip)
            .limit(limit)
            .order_by(Agent.created_at.desc())
        )
        agents = list(result.scalars().all())

        return agents, total

    async def list_all(self, skip: int = 0, limit: int = 20, active_only: bool = False) -> tuple[list[Agent], int]:
        """
        List all agents with pagination.
        
        Returns:
            Tuple of (agents list, total count)
        """
        query = select(Agent)
        
        if active_only:
            query = query.where(Agent.is_active == True)
        
        # Get total count
        count_result = await self.db.execute(
            select(func.count()).select_from(Agent).where(Agent.is_active == True if active_only else True)
        )
        total = count_result.scalar_one()

        # Get agents
        result = await self.db.execute(
            query.offset(skip).limit(limit).order_by(Agent.created_at.desc())
        )
        agents = list(result.scalars().all())

        return agents, total

    async def create(
        self,
        name: str,
        email: str,
        phone: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Agent:
        """Create a new agent."""
        agent = Agent(
            name=name,
            email=email,
            phone=phone,
            meta_data=metadata if metadata else None,
        )

        self.db.add(agent)
        await self.db.flush()
        await self.db.refresh(agent)

        return agent

    async def update(self, agent: Agent) -> Agent:
        """Update an existing agent."""
        self.db.add(agent)
        await self.db.flush()
        await self.db.refresh(agent)
        return agent

    async def delete(self, agent: Agent) -> None:
        """Delete an agent."""
        await self.db.delete(agent)
        await self.db.flush()
