"""Integration tests for database session lifecycle and health verification."""

import pytest
from sqlalchemy import text
from app.database.connection import check_database_health, get_db_session


@pytest.mark.asyncio
async def test_database_health_check():
    """Verify live database health check against PostgreSQL."""
    healthy, status_str = await check_database_health()
    assert healthy is True
    assert status_str == "healthy"


@pytest.mark.asyncio
async def test_db_session_lifecycle():
    """Verify asynchronous session acquisition, query execution, and release."""
    async for session in get_db_session():
        result = await session.execute(text("SELECT 1 AS num"))
        row = result.mappings().one()
        assert row["num"] == 1


@pytest.mark.asyncio
async def test_db_session_rollback_on_error():
    """Ensure session rolls back cleanly if an exception is raised within the context."""
    with pytest.raises(RuntimeError):
        async for session in get_db_session():
            await session.execute(text("SELECT 1"))
            raise RuntimeError("Simulated transaction failure")
