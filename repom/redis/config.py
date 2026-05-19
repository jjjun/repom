"""Redis configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RedisContainerConfig:
    """Redis Docker container settings."""

    container_name: Optional[str] = field(default=None)
    host_port: int = field(default=6379)
    volume_name: Optional[str] = field(default=None)
    image: str = field(default="redis:7-alpine")

    def get_container_name(self) -> str:
        """Return the container name."""
        return self.container_name or "repom_redis"

    def get_volume_name(self) -> str:
        """Return the Docker volume name."""
        return self.volume_name or f"{self.get_container_name()}_data"


@dataclass
class RedisConfig:
    """Redis connection and container settings."""

    host: str = field(default="localhost")
    port: int = field(default=6379)
    password: Optional[str] = field(default=None)
    database: int = field(default=0)
    container: RedisContainerConfig = field(default_factory=RedisContainerConfig)


__all__ = [
    "RedisConfig",
    "RedisContainerConfig",
]
