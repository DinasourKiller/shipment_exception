"""Database Connection & Session Management Module.

Provides SQLAlchemy 2.x asynchronous engine, session factory,
FastAPI dependency injection, and active connection health verification.
"""

from typing import AsyncGenerator, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger("control_tower.database")
settings = get_settings()

# Initialize Async Engine with connection pooling and health ping
async_engine: AsyncEngine = create_async_engine(
    settings.async_database_url,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_pre_ping=True,
    echo=settings.DEBUG,
    future=True,
)

# Async session factory
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an asynchronous database session.

    Enforces transactional boundary: commits on success, rollbacks on exception.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> Tuple[bool, Optional[str]]:
    """Verify live PostgreSQL connectivity by executing a lightweight query."""
    try:
        async with async_engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            scalar = result.scalar()
            await conn.rollback()
            if scalar == 1:
                return True, "healthy"
            return False, f"Unexpected healthcheck return: {scalar}"
    except Exception as exc:
        logger.error(f"Database health verification failed: {exc}", exc_info=True)
        return False, str(exc)
