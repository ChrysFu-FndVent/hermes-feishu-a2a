from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from .models import AgentRegistration


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HERMES_", env_file=".env", extra="ignore")

    env: str = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=8080, ge=1, le=65535)
    database_url: str = "sqlite:///./data/hermes.db"
    log_level: str = "INFO"
    internal_api_token: SecretStr = SecretStr("")
    agents_config_path: Path = Path("config/agents.yaml")
    max_concurrency: int = Field(default=8, ge=1, le=128)
    default_task_timeout_seconds: float = Field(default=120, gt=0, le=3600)
    webhook_tolerance_seconds: int = Field(default=300, ge=0, le=3600)

    feishu_domain: str = "https://open.feishu.cn"
    feishu_app_id: str = ""
    feishu_app_secret: SecretStr = SecretStr("")
    feishu_encrypt_key: SecretStr = SecretStr("")
    feishu_verification_token: SecretStr = SecretStr("")
    feishu_webhook_signature_required: bool = True
    feishu_allowed_chat_ids: Annotated[list[str], NoDecode] = Field(default_factory=list)
    feishu_owner_open_ids: Annotated[list[str], NoDecode] = Field(default_factory=list)
    feishu_file_intake_agent_id: str = ""
    feishu_file_max_count: int = Field(default=8, ge=1, le=8)
    feishu_file_max_bytes: int = Field(default=20 * 1024 * 1024, ge=1024, le=100 * 1024 * 1024)
    feishu_file_max_uncompressed_bytes: int = Field(
        default=100 * 1024 * 1024, ge=1024, le=500 * 1024 * 1024
    )
    feishu_file_max_extracted_chars: int = Field(default=60000, ge=1000, le=500000)
    feishu_file_max_total_chars: int = Field(default=120000, ge=1000, le=1000000)
    feishu_file_max_agent_chars: int = Field(default=30000, ge=1000, le=100000)
    feishu_file_result_reply_chars: int = Field(default=24000, ge=1000, le=50000)
    feishu_file_allowed_extensions: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [".pdf", ".docx", ".txt", ".md", ".csv", ".json"]
    )

    @field_validator(
        "feishu_allowed_chat_ids",
        "feishu_owner_open_ids",
        "feishu_file_allowed_extensions",
        mode="before",
    )
    @classmethod
    def parse_csv(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError("expected a comma-separated string or a list of strings")

    @field_validator("feishu_file_allowed_extensions")
    @classmethod
    def normalize_extensions(cls, value: list[str]) -> list[str]:
        return [item.lower() if item.startswith(".") else f".{item.lower()}" for item in value]

    def validate_for_production(self) -> list[str]:
        errors: list[str] = []
        if not self.has_valid_internal_api_token():
            errors.append(
                "HERMES_INTERNAL_API_TOKEN must be a random value of at least 32 characters"
            )
        if self.feishu_webhook_signature_required:
            encrypt_key = self.feishu_encrypt_key.get_secret_value()
            if not encrypt_key or _is_placeholder(encrypt_key):
                errors.append(
                    "HERMES_FEISHU_ENCRYPT_KEY is required when webhook signatures are enabled"
                )
        verification_token = self.feishu_verification_token.get_secret_value()
        if not verification_token or _is_placeholder(verification_token):
            errors.append("HERMES_FEISHU_VERIFICATION_TOKEN is required")
        if not self.feishu_app_id or _is_placeholder(self.feishu_app_id):
            errors.append("HERMES_FEISHU_APP_ID is required")
        app_secret = self.feishu_app_secret.get_secret_value()
        if not app_secret or _is_placeholder(app_secret):
            errors.append("HERMES_FEISHU_APP_SECRET is required")
        if not self.feishu_allowed_chat_ids or any(
            _is_placeholder(value) for value in self.feishu_allowed_chat_ids
        ):
            errors.append("HERMES_FEISHU_ALLOWED_CHAT_IDS must contain real chat IDs")
        if not self.feishu_owner_open_ids or any(
            _is_placeholder(value) for value in self.feishu_owner_open_ids
        ):
            errors.append("HERMES_FEISHU_OWNER_OPEN_IDS must contain real owner open IDs")
        return errors

    def has_valid_internal_api_token(self) -> bool:
        internal_token = self.internal_api_token.get_secret_value()
        return len(internal_token) >= 32 and not _is_placeholder(internal_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return not normalized or any(
        marker in normalized for marker in ("replace", "example", "xxx", "change-me")
    )


def load_agent_config(path: str | Path) -> list[AgentRegistration]:
    try:
        with Path(path).open(encoding="utf-8") as handle:
            document = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid agent config YAML: {exc}") from exc
    if not isinstance(document, dict):
        raise ValueError("agents.yaml must contain a mapping")
    agents = document.get("agents", [])
    if not isinstance(agents, list):
        raise ValueError("agents.yaml must contain an 'agents' list")
    registrations = [AgentRegistration.model_validate(agent) for agent in agents]
    ids = [registration.id for registration in registrations]
    if len(ids) != len(set(ids)):
        raise ValueError("agent ids must be unique")
    for registration in registrations:
        targets = [registration.endpoint or "", registration.open_id or ""]
        chat_id = registration.metadata.get("chat_id")
        if isinstance(chat_id, str):
            targets.append(chat_id)
        if any(_is_placeholder(value) for value in targets if value):
            raise ValueError(f"agent {registration.id} contains placeholder transport values")
    return registrations
