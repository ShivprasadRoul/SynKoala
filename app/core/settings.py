from functools import cached_property

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Figma OAuth (account-linking flow, not sign-in — planning/01-auth.md)
    figma_client_id: str | None = None
    figma_client_secret: str | None = None
    figma_redirect_uri: str | None = None
    figma_token_encryption_key: str | None = None

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
