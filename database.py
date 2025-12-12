# ============================================================
# HORUS DATABASE LAYER (PostgreSQL + SQLAlchemy Async)
# ============================================================

import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config.config import DATABASE_URL


# ------------------------------------------------------------
# Base Model Class
# ------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ------------------------------------------------------------
# Create the Async Engine
# ------------------------------------------------------------
engine = create_async_engine(
    DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    future=True,
    echo=False,
    pool_size=10,
    max_overflow=20
)

# ------------------------------------------------------------
# Session Factory
# ------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)


# ------------------------------------------------------------
# Dependency (used by all services)
# ------------------------------------------------------------
async def get_session():
    async with AsyncSessionLocal() as session:
        yield session
