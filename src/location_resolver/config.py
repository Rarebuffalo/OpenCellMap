"""Application configuration management using Pydantic Settings."""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application and environment settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project metadata
    PROJECT_NAME: str = "Open Location Resolution Infrastructure"
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database Configuration (PostgreSQL + PostGIS)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "location_resolver"
    POSTGRES_USER: str = "olr_user"
    POSTGRES_PASSWORD: str = "olr_password"
    DB_POOL_MIN_SIZE: int = 2
    DB_POOL_MAX_SIZE: int = 10

    # External Data Sources
    OPENCELLID_API_KEY: str = Field(default="", description="OpenCelliD API access token")

    # Local Ingestion Paths
    RAW_DATA_DIR: Path = Path("data/raw")
    PROCESSED_DATA_DIR: Path = Path("data/processed")
    REPORTS_DIR: Path = Path("reports/dataset-inspection")

    @property
    def database_url(self) -> str:
        """Construct the PostgreSQL connection string."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
