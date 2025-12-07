"""Configuration loader for the Telegram group management bot."""
from dataclasses import dataclass
import os
from typing import Optional


def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    value = os.environ.get(key)
    if value is None or value.strip() == "":
        return default
    return value


@dataclass
class Settings:
    """Runtime settings resolved from environment variables."""

    bot_token: str
    warnings_limit: int = 3
    storage_path: str = "./warnings.json"
    admin_only_links: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        token = _env("TELEGRAM_BOT_TOKEN")
        if not token:
            raise RuntimeError(
                "Set TELEGRAM_BOT_TOKEN in your environment (use .env.example as a template)."
            )

        limit_raw = _env("WARNINGS_LIMIT", "3")
        try:
            warnings_limit = max(1, int(limit_raw))
        except ValueError as exc:
            raise RuntimeError("WARNINGS_LIMIT must be an integer") from exc

        storage_path = _env("WARNINGS_STORAGE", "./warnings.json")
        admin_only_links = _env("ADMIN_ONLY_LINKS", "true").lower() in {"1", "true", "yes"}

        return cls(
            bot_token=token,
            warnings_limit=warnings_limit,
            storage_path=storage_path,
            admin_only_links=admin_only_links,
        )
