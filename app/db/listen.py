import asyncpg

from app.core.settings import settings


def _listen_dsn() -> str:
    """asyncpg.connect() wants a plain postgresql:// URL — the +asyncpg suffix in
    settings.database_url is only meaningful to SQLAlchemy's dialect loader."""
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def get_listen_connection() -> asyncpg.Connection:
    """A dedicated raw connection for LISTEN (planning/03-data-model-and-infra.md
    "Realtime") — separate from the SQLAlchemy pool since it has to stay open and
    idle-waiting for NOTIFY, which a pooled/short-lived session connection isn't for."""
    return await asyncpg.connect(_listen_dsn())
