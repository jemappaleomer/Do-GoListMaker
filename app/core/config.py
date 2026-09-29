from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

class Settings(BaseSettings):
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SECRET_KEY: str = "default-secret-key-change-in-production"
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

