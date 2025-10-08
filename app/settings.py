"""Application settings using pydantic-settings."""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore")

    # Application
    app_env: str = Field(default="dev", description="Application environment")
    app_secret_key: str = Field(default="dev-secret-key-change-in-production", description="Secret key for JWT and encryption")
    jwt_access_expire_min: int = Field(default=30, description="JWT access token expiration in minutes")
    jwt_refresh_expire_days: int = Field(default=7, description="JWT refresh token expiration in days")

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./dev.db", description="Primary database connection string"
    )
    sqlite_url: str = Field(default="sqlite+aiosqlite:///./dev.db", description="SQLite fallback connection")

    # MT5 Manager SDK (optional for development)
    mt5_dll_path: str = Field(default="", description="Path to MT5 Manager API DLL")
    mt5_manager_host: str = Field(default="localhost", description="MT5 Manager server host")
    mt5_manager_port: int = Field(default=443, description="MT5 Manager server port")
    mt5_manager_login: int = Field(default=0, description="MT5 Manager login")
    mt5_manager_password: str = Field(default="", description="MT5 Manager password")
    mt5_cert_path: str = Field(default="", description="MT5 certificate path (optional)")
    mt5_cert_password: str = Field(default="", description="MT5 certificate password (optional)")
    mt5_connection_timeout: int = Field(default=30, description="MT5 connection timeout in seconds")
    mt5_max_retries: int = Field(default=3, description="Maximum retry attempts for MT5 operations")

    # Pipedrive
    pipedrive_base_url: str = Field(default="https://api.pipedrive.com/v1", description="Pipedrive API base URL")
    pipedrive_client_id: str = Field(default="", description="Pipedrive OAuth client ID")
    pipedrive_client_secret: str = Field(default="", description="Pipedrive OAuth client secret")
    pipedrive_redirect_uri: str = Field(
        default="http://localhost:8000/oauth/pipedrive/callback", description="Pipedrive OAuth redirect URI"
    )
    pipedrive_api_token: str = Field(default="", description="Pipedrive API token (for dev)")
    pipedrive_webhook_secret: str = Field(default="", description="Pipedrive webhook secret for validation")

    # CORS
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:8000", description="CORS allowed origins")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def use_postgres(self) -> bool:
        """Check if PostgreSQL is configured."""
        return "postgresql" in self.database_url.lower()

    @property
    def effective_database_url(self) -> str:
        """Get the effective database URL (fallback to SQLite if needed)."""
        if self.use_postgres:
            return self.database_url
        return self.sqlite_url


# Global settings instance
settings = Settings()
