"""
PAW Configuration — Centralized settings management.

All configuration flows through here. Environment variables take precedence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PawSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PAW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Paths
    paw_home: Path = Field(
        default_factory=lambda: Path.home() / ".paw",
        description="PAW home directory",
    )
    config_path: Path | None = Field(
        default=None,
        description="Explicit config file path",
    )

    # Database
    database_url: str = Field(
        default="",
        description="SQLite database URL (empty = default in paw_home)",
    )

    # CLI
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level",
    )
    log_format: Literal["json", "console"] = Field(
        default="console",
        description="Log output format",
    )

    # Context
    max_context_tokens: int = Field(
        default=12000,
        description="Maximum tokens for context budget",
    )

    # Model routing (Phase 4+)
    default_model_role: str = Field(
        default="fast",
        description="Default model role for tasks",
    )

    # Policy (Phase 6+)
    default_policy_mode: Literal["allow", "deny", "ask"] = Field(
        default="ask",
        description="Default policy for unrecognized capabilities",
    )

    # Skill fabric (Phase 2+)
    skills_dir: Path | None = Field(
        default=None,
        description="Custom skills directory (default: paw_home/skills)",
    )

    # Knowledge engine (Phase 7+)
    knowledge_dir: Path | None = Field(
        default=None,
        description="Knowledge sources directory (default: paw_home/knowledge)",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        self.paw_home.mkdir(parents=True, exist_ok=True)
        if self.skills_dir:
            self.skills_dir.mkdir(parents=True, exist_ok=True)
        if self.knowledge_dir:
            self.knowledge_dir.mkdir(parents=True, exist_ok=True)

    @property
    def db_path(self) -> Path:
        if self.database_url and self.database_url.startswith("sqlite:///"):
            return Path(self.database_url[10:])
        return self.paw_home / "paw.db"

    @property
    def skills_path(self) -> Path:
        return self.skills_dir or (self.paw_home / "skills")

    @property
    def knowledge_path(self) -> Path:
        return self.knowledge_dir or (self.paw_home / "knowledge")

    @property
    def artifacts_path(self) -> Path:
        p = self.paw_home / "artifacts"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def cache_path(self) -> Path:
        p = self.paw_home / "cache"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def logs_path(self) -> Path:
        p = self.paw_home / "logs"
        p.mkdir(parents=True, exist_ok=True)
        return p


# Global settings instance
settings = PawSettings()
