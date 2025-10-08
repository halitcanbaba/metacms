"""Test health endpoints."""
import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    """Test the main health check endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_database_health(client):
    """Test the database health check endpoint."""
    response = await client.get("/health/database")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
