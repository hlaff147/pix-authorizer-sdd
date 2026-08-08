from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    aws_region: str = "us-east-1"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    dynamodb_endpoint_url: Optional[str] = "http://localhost:4566"
    dynamodb_table_name: str = "pix_transactions_store"
    max_single_transfer: float = 5000.00
    max_daily_limit: float = 20000.00

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
