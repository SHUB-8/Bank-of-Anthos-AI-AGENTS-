import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# All config is loaded from Kubernetes manifests secrets only
DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_async_engine(DATABASE_URL, echo=False)

# Use modern async_sessionmaker
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency to get a DB session, using the correct modern pattern."""
    async with async_session_factory() as session:
        yield session