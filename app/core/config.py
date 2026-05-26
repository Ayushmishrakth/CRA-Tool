"""
Centralized application settings — Microsoft Entra ID + CRA JWT.

Pydantic Settings best practices:
- Explicit fields for every supported .env variable
- extra="ignore" so unknown env keys never crash startup
- @lru_cache singleton for performance
- Validators for security-sensitive values
"""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables and .env.

    Env names are case-insensitive (ORGANIZATION_NAME → organization_name).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Prevent crashes when .env has extra keys (e.g. future vars, comments mis-parsed)
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "CRA Backend"
    app_version: str = "2.0.0"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    organization_name: str = Field(
        default="",
        description="Customer organization display name (CRA branding / reports)",
    )

    # --- CORS (CRA React frontend) ---
    cors_origins: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        description="Allowed origins for browser clients (MSAL React)",
    )

    # --- Database ---
    database_url: str = "sqlite:///./cra.db"

    # --- CRA internal JWT ---
    secret_key: str = Field(
        default="CHANGE-ME-use-openssl-rand-hex-32",
        description="Signing key for CRA JWT tokens",
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- Microsoft Entra ID ---
    azure_client_id: str = Field(
        default="00000000-0000-0000-0000-000000000000",
        description="App registration Application (client) ID",
    )
    azure_tenant_id: str = Field(
        default="common",
        description="Entra tenant ID, or 'common' / 'organizations' for multi-tenant",
    )
    azure_client_secret: str | None = None
    azure_authority: str | None = None
    azure_redirect_uri: str | None = None

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("SECRET_KEY must not be empty")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        """Allow comma-separated string in .env: CORS_ORIGINS=http://localhost:3000,..."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def microsoft_authority(self) -> str:
        if self.azure_authority:
            return self.azure_authority.rstrip("/")
        return f"https://login.microsoftonline.com/{self.azure_tenant_id}"

    @property
    def microsoft_jwks_uri(self) -> str:
        return f"{self.microsoft_authority}/discovery/v2.0/keys"


@lru_cache
def get_settings() -> Settings:
    """Cached settings — call get_settings() in tests to override via env."""
    return Settings()


settings = get_settings()
