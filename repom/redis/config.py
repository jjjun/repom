"""Redis configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote


@dataclass
class RedisContainerConfig:
    """Redis Docker container settings."""

    container_name: Optional[str] = field(default=None)
    host_port: Optional[int] = field(default=None)
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

    host: str = field(default="127.0.0.1")
    port: int = field(default=6379)
    password: Optional[str] = field(default=None, repr=False)
    database: int = field(default=0)
    allow_insecure_remote: bool = field(default=False)
    container: RedisContainerConfig = field(default_factory=RedisContainerConfig)

    @property
    def published_port(self) -> int:
        """Return the host port used to publish the Redis container."""

        if self.container.host_port is not None:
            return self.container.host_port
        return self.port

    def connection_kwargs(self) -> dict[str, str | int | None]:
        """Return connection arguments for redis-py clients."""
        return {
            "host": self.host,
            "port": self.port,
            "db": self.database,
            "password": self.password or None,
        }

    def url(self, include_password: bool = False) -> str:
        """Return a Redis URL, including the password only when requested."""
        credentials = ""
        if include_password and self.password:
            credentials = f":{quote(self.password, safe='')}@"
        return f"redis://{credentials}{self.host}:{self.port}/{self.database}"

    def safe_url(self) -> str:
        """Return a Redis URL with any configured password masked."""
        credentials = ":***@" if self.password else ""
        return f"redis://{credentials}{self.host}:{self.port}/{self.database}"

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
