import os

# Settings is required-field-strict on purpose (fail fast on missing prod config —
# planning/00-overview.md). Tests never touch a real DB or real Supabase project, so
# these are dummy-but-well-formed values, set before `app` is imported anywhere.
os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault(
    "FIGMA_TOKEN_ENCRYPTION_KEY",
    "7h4uuBrbi5httHBTemCR3MHjdymrVTJ78GRO2mWAo7w=",
)

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
