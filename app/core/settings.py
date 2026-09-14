import os
from functools import cached_property

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# pydantic-settings parses `.env` into this class's own fields but never exports it to
# the real process environment. Pydantic AI's model providers (e.g. OpenRouterProvider,
# planning/05-stimulus-engine.md) read their API keys via `os.getenv` directly, so `.env`
# has to land there too — this is a no-op if the vars are already set (e.g. in prod).
load_dotenv()
# Pydantic AI prints an interactive-looking banner on every first call per agent unless
# this is set — noise in a worker's logs, not a REPL.
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")


class Settings(BaseSettings):
    """See ../../../planning/00-overview.md and ../../../planning/01-auth.md for what
    each of these backs and why (Supabase as the backing store, JWKS-based auth)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    supabase_url: str
    supabase_service_role_key: str | None = None
    database_url: str
    supabase_jwt_audience: str = "authenticated"
    supabase_storage_bucket: str = "stimuli"

    # Web App (planning/12-web-app.md) — a browser at a different origin than the API
    cors_allowed_origins: list[str] = ["http://localhost:3000"]

    # Figma OAuth (account-linking flow, not sign-in — planning/01-auth.md)
    figma_client_id: str | None = None
    figma_client_secret: str | None = None
    figma_redirect_uri: str | None = None
    figma_token_encryption_key: str | None = None

    # Stimulus Engine's VisionProvider (planning/05-stimulus-engine.md) — a Pydantic AI
    # model identifier. Routed through OpenRouter (one API key covers many underlying
    # models) — Pydantic AI reads OPENROUTER_API_KEY itself, not a setting here.
    vision_model: str = "openrouter:openai/gpt-4o-mini"

    # Insight Engine's InsightProvider (planning/11-insight-engine.md) — LLD §29
    # recommends a frontier-tier model for final insight synthesis specifically,
    # unlike the mid-tier vision/participant-simulation models above.
    insight_model: str = "openrouter:openai/gpt-4o"

    # AudienceEngine's real-data grounding (planning/04-audience-engine.md) — the
    # compiled audience-prior graph JSON (survey datasets like WVS/Findex, compiled
    # offline; see app/core/persona_prior/), stored as a private Supabase Storage
    # object and referenced the same "{bucket}/{path}" way as `screens.image_url`
    # (app/core/storage.py). Leave unset to disable: audience generation falls back
    # to the qualitative-band statistical sampler instead of failing at import time,
    # same as an unset FIGMA_CLIENT_ID above.
    persona_prior_graph_storage_path: str | None = None

    @cached_property
    def supabase_jwt_issuer(self) -> str:
        return f"{self.supabase_url}/auth/v1"

    @cached_property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_url}/auth/v1/.well-known/jwks.json"

    @cached_property
    def supabase_storage_url(self) -> str:
        return f"{self.supabase_url}/storage/v1"


settings = Settings()
