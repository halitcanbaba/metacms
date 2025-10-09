"""Customers repository for database operations."""
from typing import Any
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Customer


class CustomersRepository:
    """Repository for Customer model operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, customer_id: int) -> Customer | None:
        """Get customer by ID."""
        result = await self.db.execute(
            select(Customer).where(Customer.id == customer_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Customer | None:
        """Get customer by email."""
        result = await self.db.execute(select(Customer).where(Customer.email == email))
        return result.scalar_one_or_none()

    async def search(self, search_term: str, skip: int = 0, limit: int = 20) -> tuple[list[Customer], int]:
        """
        Search customers by name, email, or phone.
        
        Returns:
            Tuple of (customers list, total count)
        """
        # Build search filter
        search_filter = or_(
            Customer.name.ilike(f"%{search_term}%"),
            Customer.email.ilike(f"%{search_term}%"),
            Customer.phone.ilike(f"%{search_term}%"),
        )

        # Get total count
        count_result = await self.db.execute(select(func.count()).select_from(Customer).where(search_filter))
        total = count_result.scalar_one()

        # Get customers
        result = await self.db.execute(
            select(Customer).where(search_filter).offset(skip).limit(limit).order_by(Customer.created_at.desc())
        )
        customers = list(result.scalars().all())

        return customers, total

    async def list_all(self, skip: int = 0, limit: int = 20) -> tuple[list[Customer], int]:
        """
        List all customers with pagination.
        
        Returns:
            Tuple of (customers list, total count)
        """
        # Get total count
        count_result = await self.db.execute(select(func.count()).select_from(Customer))
        total = count_result.scalar_one()

        # Get customers
        result = await self.db.execute(
            select(Customer).offset(skip).limit(limit).order_by(Customer.created_at.desc())
        )
        customers = list(result.scalars().all())

        return customers, total

    async def create(
        self,
        name: str,
        email: str | None = None,
        phone: str | None = None,
        address: str | None = None,
        tags: list[str] | None = None,
        external_ids: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Customer:
        """Create a new customer."""
        customer = Customer(
            name=name, 
            email=email, 
            phone=phone, 
            address=address,
            tags=tags, 
            external_ids=external_ids or {}, 
            metadata=metadata or {}
        )

        self.db.add(customer)
        await self.db.flush()
        await self.db.refresh(customer)

        return customer

    async def update(self, customer: Customer) -> Customer:
        """Update an existing customer."""
        self.db.add(customer)
        await self.db.flush()
        await self.db.refresh(customer)
        return customer

    async def delete(self, customer: Customer) -> None:
        """Delete a customer."""
        await self.db.delete(customer)
        await self.db.flush()

    async def update_external_id(self, customer_id: int, service: str, external_id: str) -> Customer | None:
        """Update external ID for a customer."""
        customer = await self.get_by_id(customer_id)
        if customer:
            if customer.external_ids is None:
                customer.external_ids = {}
            customer.external_ids[service] = external_id
            return await self.update(customer)
        return None
