import os

from pydantic import Field, model_validator
from pydantic import field_validator, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class SystemSettings(BaseSettings):
    slack_app_token: str = Field(..., description="Slack app token")

    queue_host: str = Field("127.0.0.1", description="Queue host")
    queue_port: int = Field(50000, description="Queue port")
    queue_authkey: bytes = Field(default=b"change-me", description="Queue authkey")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("slack_app_token", mode="before")
    @classmethod
    def parse_slack_token(cls, v: str) -> str:
        """Slack token'ı doğrular."""
        if not v.startswith("xoxb-") and not v.startswith("xapp-") and not v.startswith("xoxp-"):
            raise ValueError("Slack token geçerli değil (xoxb-, xapp- veya xoxp- ile başlamalı)")
        return v

    @field_validator("queue_authkey", mode="before")
    @classmethod
    def parse_queue_authkey(cls, v: str | bytes) -> bytes:
        """Env'den string gelirse bytes'a çevirir."""
        if isinstance(v, str):
            return v.encode("utf-8")
        return v

    @model_validator(mode="after")
    def reject_default_authkey_in_production(self) -> "SystemSettings":
        """Prod ortamında varsayılan QUEUE_AUTHKEY kabul edilmez."""
        if os.environ.get("ENV") == "production" and self.queue_authkey == b"change-me":
            raise ValueError(
                "Production'da QUEUE_AUTHKEY ortam değişkeni güçlü bir değerle ayarlanmalı."
            )
        return self


Settings = SystemSettings  # alias for imports
_settings: SystemSettings = SystemSettings()

def get_settings(reload: bool = False) -> SystemSettings:
    """Sistem ayarlarını döndürür."""
    global _settings
    if _settings is None or reload:
        _settings = SystemSettings()
    return _settings