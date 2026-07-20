from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HERMES_", env_file=".env", extra="ignore")

    env: str = "development"
    host: str = "0.0.0.0"
    port: int = Field(default=8080, ge=1, le=65535)
    database_url: str = "sqlite:///./data/hermes.db"
    log_level: str = "INFO"
    secret_key: SecretStr = SecretStr("change-me-in-production")
    internal_api_token: SecretStr = SecretStr("")
    max_concurrency: int = Field(default=8, ge=1, le=128)
    default_task_timeout_seconds: float = Field(default=120, gt=0, le=3600)
    webhook_tolerance_seconds: int = Field(default=300, ge=0, le=3600)

    feishu_domain: str = "https://open.feishu.cn"
    feishu_app_id: str = ""
    feishu_app_secret: SecretStr = SecretStr("")
    feishu_encrypt_key: SecretStr = SecretStr("")
    feishu_verification_token: SecretStr = SecretStr("")
    feishu_webhook_signature_required: bool = True
    feishu_allowed_chat_ids: list[str] = Field(default_factory=list)
    feishu_owner_open_ids: list[str] = Field(default_factory=list)
    feishu_token_cache_path: Path = Path("./data/feishu-token.json")
    secret_encryption_key: SecretStr = SecretStr("")

    @field_validator("feishu_allowed_chat_ids", "feishu_owner_open_ids", mode="before")
    @classmethod
    def parse_csv(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError("expected a comma-separated string or a list of strings")

    def validate_for_production(self) -> list[str]:
        errors: list[str] = []
        if (
            self.env == "production"
            and self.secret_key.get_secret_value() == "change-me-in-production"
        ):
            errors.append("HERMES_SECRET_KEY must be changed in production")
        if (
            self.feishu_webhook_signature_required
            and not self.feishu_verification_token.get_secret_value()
        ):
            errors.append(
                "HERMES_FEISHU_VERIFICATION_TOKEN is required when signatures are enabled"
            )
        if not self.internal_api_token.get_secret_value():
            errors.append("HERMES_INTERNAL_API_TOKEN is required for protected APIs")
        return errors


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_agent_config(path: str | Path) -> list[dict[str, object]]:
    with Path(path).open(encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}
    agents = document.get("agents", [])
    if not isinstance(agents, list):
        raise ValueError("agents.yaml must contain an 'agents' list")
    return agents
