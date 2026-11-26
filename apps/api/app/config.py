from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_ROOT / ".env", extra="ignore")

    app_name: str = "KinetiQ Para API"
    database_url: str = f"sqlite:///{(API_ROOT / 'data' / 'kinetiq.db').as_posix()}"
    storage_dir: Path = API_ROOT / "data" / "storage"
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12
    cors_origins: list[str] = ["http://localhost:3000"]

    # Gemini: key comes from .env, model ID is pinned here once confirmed in the docs.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"


settings = Settings()
