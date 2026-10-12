"""
Central configuration. Every secret and environment-specific value is loaded
from the environment (or a local .env file) — nothing sensitive is hardcoded.

See .env.example for the full list. The app refuses to start with insecure
defaults in production (see validate_production()).
"""
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Runtime ---
    ENV: str = "dev"  # dev | prod
    APP_NAME: str = "EasyPhoneUnlock Cloud Admin API"
    APP_VERSION: str = "2.0.0"

    # --- Database ---
    # Default to a local SQLite file for easy dev; set a postgres URL in prod,
    # e.g. postgresql+psycopg2://user:pass@host:5432/epu
    DATABASE_URL: str = "sqlite:///./backend/easyphoneunlock.db"

    # --- JWT / sessions ---
    JWT_SECRET: str = "CHANGE_ME_INSECURE_DEV_SECRET"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_MIN: int = 60          # short-lived access token
    REFRESH_TOKEN_TTL_DAYS: int = 14        # long-lived refresh token
    OPERATION_GRANT_TTL_SEC: int = 300      # a grant is only usable for 5 min

    # --- Admin bootstrap ---
    # On first run the single superadmin is created from these. The app refuses
    # to start in prod if the password is empty or the known-weak default.
    ADMIN_USERNAME: str = "admin"
    ADMIN_BOOTSTRAP_PASSWORD: str = ""

    # --- Payload vault ---
    # Directory (outside the web root, git-ignored) holding encrypted DA/exploit
    # binaries, and the Fernet key used to decrypt them.
    PAYLOAD_DIR: str = "./backend/vault"
    PAYLOAD_ENC_KEY: str = ""  # urlsafe base64 32-byte Fernet key

    # --- CORS ---
    # Comma-separated list, e.g. "https://panel.example.com,https://app.example.com"
    CORS_ORIGINS: str = ""

    # --- Rate limiting ---
    LOGIN_MAX_ATTEMPTS: int = 10
    LOGIN_LOCKOUT_MIN: int = 15

    # --- Credits ---
    REGISTER_BONUS_CREDITS: int = 10

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return []
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_prod(self) -> bool:
        return self.ENV.lower() in ("prod", "production")

    def validate_production(self) -> None:
        """Fail fast on insecure config when running in production."""
        problems = []
        if self.JWT_SECRET in ("", "CHANGE_ME_INSECURE_DEV_SECRET") or len(self.JWT_SECRET) < 32:
            problems.append("JWT_SECRET must be set to a strong (>=32 char) random value.")
        if not self.ADMIN_BOOTSTRAP_PASSWORD or self.ADMIN_BOOTSTRAP_PASSWORD in ("admin", "admin123"):
            problems.append("ADMIN_BOOTSTRAP_PASSWORD must be set and must not be a default.")
        if not self.PAYLOAD_ENC_KEY:
            problems.append("PAYLOAD_ENC_KEY must be set (generate with: python -m backend.core.vault keygen).")
        if not self.cors_origins_list:
            problems.append("CORS_ORIGINS must list explicit allowed origins (never '*').")
        if self.DATABASE_URL.startswith("sqlite"):
            problems.append("Use PostgreSQL in production (SQLite can't do row-level locking under load).")
        if problems:
            raise RuntimeError(
                "Refusing to start in production with insecure configuration:\n  - "
                + "\n  - ".join(problems)
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
