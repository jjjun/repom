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
    # Bind the published port to 0.0.0.0 instead of 127.0.0.1. Only enable
    # this for a project that genuinely needs LAN access to this container;
    # the default keeps it reachable from the developer machine only.
    expose_to_lan: bool = field(default=False)

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
    password: Optional[str] = field(default=None, repr=False)
    database: int = field(default=0)
    container: RedisContainerConfig = field(default_factory=RedisContainerConfig)

    def __repr__(self) -> str:
        password_display = "***" if self.password else "None"
        return (
            f"{self.__class__.__name__}(host={self.host!r}, port={self.port!r}, "
            f"password={password_display}, database={self.database!r}, "
            f"container={self.container!r})"
        )


__all__ = [
    "RedisConfig",
    "RedisContainerConfig",
]
