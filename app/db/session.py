from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import settings

# pool_size/max_overflow are explicit, not SQLAlchemy's defaults (5/10 = 15 per
# engine instance) — DATABASE_URL points at Supabase's session-mode pooler,
# which caps total concurrent clients at 15 *project-wide*, not per process.
# A single long-running process (the worker, NUM_WORKERS=5 concurrent loops
# sharing this one engine) hitting the default would already be entitled to
# every slot in the whole project by itself, starving the API server, ad-hoc
# scripts, or even the Supabase dashboard's own SQL editor. 5+2 covers the
# worker's 5 concurrent loops with a little headroom, while still leaving
# room for everything else sharing the same 15-connection budget.
engine = create_async_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=2)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
