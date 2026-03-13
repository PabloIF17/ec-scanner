from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://ecscanner:secret@postgres:5432/ecscanner"
    database_url_sync: str = "postgresql+psycopg2://ecscanner:secret@postgres:5432/ecscanner"

    # Redis / Celery
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    # App
    secret_key: str = "changeme"
    environment: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

    # Discovery APIs
    securitytrails_api_key: str = ""
    virustotal_api_key: str = ""
    rapid7_data_dir: str = "/data/rapid7"

    # Enrichment APIs
    clearbit_api_key: str = ""
    zoominfo_api_key: str = ""
    apollo_api_key: str = ""

    # Outreach
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    outreach_from_email: str = ""
    outreach_from_name: str = "Inforge Security"

    # Salesforce CRM
    sf_instance_url: str = ""
    sf_access_token: str = ""

    # Scanner settings
    scan_concurrency: int = 10
    scan_rate_limit_ms: int = 2000


@lru_cache()
def get_settings() -> Settings:
    return Settings()
