import sys

from loguru import logger
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_name: str = "SimuOrg"
    secret_key: str = "fallback_secret"
    database_url: str = "sqlite:///./simuorg.db"
    groq_api_key: str = ""
    pinecone_api_key: str = ""
    pinecone_index_name: str = ""

    # Observability
    sentry_dsn_backend: str = ""
    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()

# --- Logging Configuration (Loguru) ---
# Remove default logger so we don't get double logs
logger.remove()

# If we are in production (e.g. GCP), output as Structured JSON so error aggregators can parse it perfectly.
# If in development (local), output nicely colored string logs for easy reading.
if settings.environment == "production":
    logger.add(sys.stdout, serialize=True, level="INFO")
else:
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        level="DEBUG",
    )
