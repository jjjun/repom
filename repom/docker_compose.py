"""repom extensions to the basekit Docker Compose model."""

from __future__ import annotations

from dataclasses import dataclass

from basekit.docker_compose import DockerComposeGenerator, DockerService

from repom.docker_compose_safety import quote_yaml_string


# This shim can go once basekit supports DockerService.restart.
@dataclass
class RepomDockerService(DockerService):
    """Docker Compose service with repom's restart policy field."""

    restart: str | None = None


class RepomDockerComposeGenerator(DockerComposeGenerator):
    """Render repom service fields that are not available in basekit yet."""

    def _generate_service(self, service: RepomDockerService) -> list[str]:
        lines = super()._generate_service(service)
        if service.restart is not None:
            container_name_line = f"    container_name: {service.container_name}"
            lines.insert(
                lines.index(container_name_line) + 1,
                f"    restart: {quote_yaml_string(service.restart)}",
            )
        return lines


__all__ = ["RepomDockerComposeGenerator", "RepomDockerService"]
