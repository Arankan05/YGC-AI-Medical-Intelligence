from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory for backend (location of .env)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """
    Central application configuration loaded from environment variables and backend/.env.
    """

    # Database connection URL
    DATABASE_URL: str = Field(
        default="",
        description="PostgreSQL / Supabase connection URL",
    )

    # Supabase credentials
    SUPABASE_URL: str = Field(
        default="",
        description="Supabase project URL",
    )
    SUPABASE_KEY: str = Field(
        default="",
        description="Supabase API / Anon Key",
    )
    SUPABASE_SERVICE_KEY: Optional[str] = Field(
        default=None,
        description="Supabase service_role key for server-side private storage and admin operations",
    )
    SUPABASE_JWT_SECRET: Optional[str] = Field(
        default=None,
        description="Supabase JWT secret for local token signature verification (optional)",
    )
    SUPABASE_JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Supabase JWT signing algorithm (e.g. HS256)",
    )
    SUPABASE_JWT_AUDIENCE: Optional[str] = Field(
        default="authenticated",
        description="Expected audience for Supabase JWTs (e.g. 'authenticated')",
    )

    # Storage settings
    SUPABASE_STORAGE_BUCKET: str = Field(
        default="medical-documents",
        description="Private Supabase storage bucket name for medical documents",
    )
    STORAGE_MAX_FILE_SIZE_BYTES: int = Field(
        default=25 * 1024 * 1024,  # 25 MB
        description="Maximum allowed file size in bytes (25 MB limit)",
    )

    # AI Service Settings
    AI_PROVIDER: Optional[str] = Field(
        default="gemini",
        description="AI LLM Provider (e.g. gemini, openai)",
    )
    AI_MODEL: str = Field(
        default="gemini-3.5-flash-lite",
        description="AI LLM Model Name (default: gemini-3.5-flash-lite)",
    )
    AI_API_KEY: Optional[str] = Field(
        default="",
        description="API Key for AI provider",
    )

    # Healthcare Open Data APIs
    NOMINATIM_URL: str = Field(
        default="https://nominatim.openstreetmap.org",
        description="OpenStreetMap Nominatim geocoding base URL",
    )
    OVERPASS_URL: str = Field(
        default="https://overpass-api.de/api/interpreter",
        description="Overpass API endpoint for healthcare provider discovery",
    )

    # OCR Settings
    TESSERACT_CMD: Optional[str] = Field(
        default=None,
        description="Path to Tesseract executable (e.g. C:\\Program Files\\Tesseract-OCR\\tesseract.exe)",
    )

    # Environment
    ENVIRONMENT: str = Field(
        default="development",
        description="Deployment environment (development, staging, production)",
    )

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached singleton instance of the application Settings.
    """
    return Settings()
