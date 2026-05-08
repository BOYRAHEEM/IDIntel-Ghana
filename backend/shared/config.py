"""Central configuration loaded from environment variables."""
from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "IDIntel Ghana API"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    secret_key: str  # 64-char random hex — required

    # Database
    database_url: str  # postgresql+asyncpg://user:pass@host:5432/db
    database_pool_size: int = 20
    database_max_overflow: int = 40
    database_pool_pre_ping: bool = True

    # Redis
    redis_url: str  # redis://user:pass@host:6379/0
    redis_tls: bool = True

    # Elasticsearch
    elasticsearch_url: str
    elasticsearch_api_key: str

    # Neo4j (relationship graph)
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str

    # Anthropic Claude
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_max_tokens: int = 4096

    # AWS
    aws_region: str = "af-south-1"
    aws_s3_bucket_reports: str
    aws_s3_bucket_audit: str
    aws_kms_key_id: str  # For identity encryption
    aws_kms_audit_key_id: str  # For audit log signing

    # JWT
    jwt_algorithm: str = "RS256"
    jwt_private_key_path: str
    jwt_public_key_path: str
    jwt_expiry_seconds: int = 14400  # 4 hours

    # NIA Integration
    nia_api_base_url: str
    nia_api_client_cert_path: str
    nia_api_client_key_path: str
    nia_api_ca_cert_path: str
    nia_api_timeout_seconds: int = 10

    # GIS (Immigration) Integration
    gis_api_base_url: str
    gis_api_api_key: str

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_default_per_minute: int = 100
    rate_limit_default_per_day: int = 50000

    # Security
    allowed_cors_origins: list[str] = []
    ip_allowlist_enabled: bool = True
    mtls_required: bool = True
    min_tls_version: str = "TLSv1.3"

    # Vault (HashiCorp)
    vault_addr: str = ""
    vault_token: str = ""
    vault_enabled: bool = False

    # Celery / RabbitMQ
    celery_broker_url: str
    celery_result_backend: str

    # Monitoring
    sentry_dsn: str = ""
    prometheus_enabled: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
