"""PostgreSQL and pgAdmin configuration models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PostgresContainerConfig:
    """PostgreSQL Docker container settings."""

    container_name: Optional[str] = field(default=None)
    host_port: int = field(default=5432)
    volume_name: Optional[str] = field(default=None)
    image: str = field(default="postgres:16-alpine")

    def get_container_name(self) -> str:
        """Return the container name."""
        return self.container_name or "repom_postgres"

    def get_volume_name(self) -> str:
        """Return the Docker volume name."""
        return self.volume_name or f"{self.get_container_name()}_data"


@dataclass
class PostgresConfig:
    """PostgreSQL database settings."""

    host: str = field(default="localhost")
    port: int = field(default=5432)
    user: str = field(default="repom")
    password: str = field(default="repom_dev", repr=False)
    database: Optional[str] = field(default=None)
    container: PostgresContainerConfig = field(default_factory=PostgresContainerConfig)

    def __repr__(self) -> str:
        password_display = "***" if self.password else "None"
        return (
            f"{self.__class__.__name__}(host={self.host!r}, port={self.port!r}, "
            f"user={self.user!r}, password={password_display}, "
            f"database={self.database!r}, container={self.container!r})"
        )


@dataclass
class PgAdminContainerConfig:
    """pgAdmin Docker container settings."""

    container_name: Optional[str] = field(default=None)
    host_port: int = field(default=5050)
    volume_name: Optional[str] = field(default=None)
    image: str = field(default="dpage/pgadmin4:latest")
    enabled: bool = field(default=False)

    def get_container_name(self) -> str:
        """Return the container name."""
        return self.container_name or "repom_pgadmin"

    def get_volume_name(self) -> str:
        """Return the Docker volume name."""
        return self.volume_name or f"{self.get_container_name()}_data"


@dataclass
class PgAdminConfig:
    """pgAdmin settings."""

    email: str = field(default="admin@example.com")
    password: str = field(default="admin", repr=False)
    container: PgAdminContainerConfig = field(default_factory=PgAdminContainerConfig)

    def __repr__(self) -> str:
        password_display = "***" if self.password else "None"
        return (
            f"{self.__class__.__name__}(email={self.email!r}, "
            f"password={password_display}, container={self.container!r})"
        )


__all__ = [
    "PgAdminConfig",
    "PgAdminContainerConfig",
    "PostgresConfig",
    "PostgresContainerConfig",
]
