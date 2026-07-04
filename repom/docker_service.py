"""Shared helpers for Docker-backed service management."""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from typing import Protocol

from basekit.docker_manager import DockerCommandExecutor


class DockerServiceManager(Protocol):
    """Manager interface used by the shared lifecycle wrappers."""

    def get_container_name(self) -> str:
        """Return the primary Docker container name."""

    def start(self, timeout_seconds: int = 30) -> None:
        """Start the service and wait for readiness."""

    def stop(self) -> None:
        """Stop the service containers."""

    def remove(self) -> None:
        """Remove the service containers and volumes."""

    def print_connection_info(self) -> None:
        """Print service connection details."""


ManagerFactory = Callable[[], DockerServiceManager]
GenerateFn = Callable[[], None]


def start_service(
    manager_factory: ManagerFactory,
    generate_fn: GenerateFn,
) -> None:
    """Generate service files, start the service, and print connection details."""

    generate_fn()
    manager = manager_factory()

    try:
        manager.start()
        manager.print_connection_info()
    except TimeoutError as exc:
        print(f"{exc}")
        print(f"Check logs: docker logs {manager.get_container_name()}")
        sys.exit(1)


def stop_service(manager_factory: ManagerFactory) -> None:
    """Stop the service managed by the given factory."""

    manager_factory().stop()


def remove_service(manager_factory: ManagerFactory) -> None:
    """Remove the service managed by the given factory."""

    manager_factory().remove()


def ensure_running(
    manager_factory: ManagerFactory,
    container_names: Mapping[str, str],
    generate_fn: GenerateFn,
    service_label: str,
    timeout_seconds: int,
) -> None:
    """Start a Docker-backed service when one or more containers are down."""

    try:
        running_by_label = {
            label: DockerCommandExecutor.is_container_running(container_name)
            for label, container_name in container_names.items()
        }
    except FileNotFoundError as exc:
        raise RuntimeError(
            "docker command not found. "
            "Please install Docker Desktop: "
            "https://www.docker.com/products/docker-desktop"
        ) from exc

    if all(running_by_label.values()):
        return

    status = ", ".join(
        f"{label}={'up' if is_running else 'down'}"
        for label, is_running in running_by_label.items()
    )
    print(
        f"\n[{service_label}] auto-start ({status}); "
        "generating compose and starting containers..."
    )

    try:
        generate_fn()
        manager_factory().start(timeout_seconds=timeout_seconds)
    except (TimeoutError, SystemExit) as exc:
        raise RuntimeError(
            f"Failed to start {service_label} via Docker: {exc}"
        ) from exc
