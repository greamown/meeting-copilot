from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()
pool_kwargs = (
    {"pool_size": 10, "max_overflow": 20}
    if settings.database_url.startswith("postgresql")
    else {}
)
engine = create_async_engine(settings.database_url, pool_pre_ping=True, **pool_kwargs)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
