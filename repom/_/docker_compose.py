"""Docker Compose ファイル動的生成の基盤

このモジュールは、Docker Compose 設定ファイルを Python から動的に生成するための
基盤クラスを提供します。PostgreSQL, Redis, MongoDB などの各種 Docker 環境で
再利用可能な汎用的な実装です。

Example:
    >>> from repom._.docker_compose import DockerComposeGenerator, DockerService, DockerVolume
    >>> 
    >>> # PostgreSQL サービスを定義
    >>> postgres = DockerService(
    ...     name="postgres",
    ...     image="postgres:16-alpine",
    ...     container_name="my_postgres",
    ...     environment={"POSTGRES_USER": "user", "POSTGRES_PASSWORD": "pass"},
    ...     ports=["5432:5432"],
    ...     volumes=["postgres_data:/var/lib/postgresql/data"]
    ... )
    >>> 
    >>> # Volume を定義
    >>> volume = DockerVolume(name="postgres_data")
    >>> 
    >>> # docker-compose.yml を生成
    >>> generator = DockerComposeGenerator()
    >>> generator.add_service(postgres).add_volume(volume)
    >>> yaml_content = generator.generate()
    >>> 
    >>> # ファイルに保存
    >>> from pathlib import Path
    >>> generator.write_to_file(Path("docker-compose.yml"))
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class DockerService:
    """Docker サービス設定

    Attributes:
        name: サービス名（docker-compose.yml 内での識別子）
        image: Docker イメージ名（例: "postgres:16-alpine"）
        container_name: コンテナ名（Docker コンテナの実行名）
        ports: ポートマッピング（例: ["5432:5432"]）
        environment: 環境変数（例: {"POSTGRES_USER": "user"}）
        volumes: ボリュームマウント（例: ["data:/var/lib/postgresql/data"]）
        command: コマンド (&& redis-server /config/redis.conf"）
        healthcheck: ヘルスチェック設定（例: {"test": "...", "interval": "5s"}）
        depends_on: 依存するサービス（例: {"postgres": {"condition": "service_healthy"}}）

    Example:
        >>> service = DockerService(
        ...     name="postgres",
        ...     image="postgres:16-alpine",
        ...     container_name="my_postgres",
        ...     ports=["5432:5432"],
        ...     environment={"POSTGRES_USER": "user"},
        ...     volumes=["postgres_data:/var/lib/postgresql/data"]
        ... )
    """
    name: str
    image: str
    container_name: str
    ports: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    volumes: List[str] = field(default_factory=list)
    command: Optional[str] = field(default=None)
    healthcheck: Optional[Dict] = field(default=None)
    depends_on: Optional[Dict] = field(default=None)


@dataclass
class DockerVolume:
    """Docker Volume 設定

    Attributes:
        name: Volume 名
        driver: Volume ドライバー（デフォルト: "local"）

    Example:
        >>> volume = DockerVolume(name="postgres_data")
        >>> volume = DockerVolume(name="redis_data", driver="local")
    """
    name: str
    driver: str = "local"


class DockerComposeGenerator:
    """Docker Compose ファイル生成器

    DockerService と DockerVolume を組み合わせて、docker-compose.yml を生成します。

    Attributes:
        version: docker-compose.yml のバージョン（デフォルト: "3.8"）
        services: サービスのリスト
        volumes: Volume のリスト

    Example:
        >>> generator = DockerComposeGenerator()
        >>> generator.add_service(postgres_service)
        >>> generator.add_volume(postgres_volume)
        >>> yaml_content = generator.generate()
        >>> generator.write_to_file(Path("docker-compose.yml"))
    """

    def __init__(self, version: str = "3.8"):
        """初期化

        Args:
            version: docker-compose.yml のバージョン（デフォルト: "3.8"）
        """
        self.version = version
        self.services: List[DockerService] = []
        self.volumes: List[DockerVolume] = []

    def add_service(self, service: DockerService) -> "DockerComposeGenerator":
        """サービスを追加

        Args:
            service: 追加する DockerService

        Returns:
            self（メソッドチェーン用）

        Example:
            >>> generator = DockerComposeGenerator()
            >>> generator.add_service(postgres_service).add_service(redis_service)
        """
        self.services.append(service)
        return self

    def add_volume(self, volume: DockerVolume) -> "DockerComposeGenerator":
        """Volume を追加

        Args:
            volume: 追加する DockerVolume

        Returns:
            self（メソッドチェーン用）

        Example:
            >>> generator = DockerComposeGenerator()
            >>> generator.add_volume(postgres_volume).add_volume(redis_volume)
        """
        self.volumes.append(volume)
        return self

    def generate(self) -> str:
        """docker-compose.yml の内容を生成

        Returns:
            docker-compose.yml の YAML 文字列

        Example:
            >>> generator = DockerComposeGenerator()
            >>> generator.add_service(service).add_volume(volume)
            >>> yaml_content = generator.generate()
            >>> print(yaml_content)
            version: '3.8'
            ...
        """
        lines = [f"version: '{self.version}'", "", "services:"]

        for service in self.services:
            lines.extend(self._generate_service(service))

        if self.volumes:
            lines.extend(["", "volumes:"])
            for volume in self.volumes:
                lines.append(f"  {volume.name}:")
                lines.append(f"    name: {volume.name}")
                if volume.driver != "local":
                    lines.append(f"    driver: {volume.driver}")

        return "\n".join(lines)

    def _generate_service(self, service: DockerService) -> List[str]:
        """サービス定義を生成（内部メソッド）

        Args:
            service: 生成する DockerService

        Returns:
            YAML 行のリスト
        """
        lines = [
            f"  {service.name}:",
            f"    image: {service.image}",
            f"    container_name: {service.container_name}",
        ]

        if service.environment:
            lines.append("    environment:")
            for key, value in service.environment.items():
                lines.append(f"      {key}: {value}")

        if service.ports:
            lines.append("    ports:")
            for port in service.ports:
                lines.append(f"      - \"{port}\"")

        if service.volumes:
            lines.append("    volumes:")
            for volume in service.volumes:
                lines.append(f"      - {volume}")

        if service.command:
            lines.append(f"    command: {service.command}")

        if service.healthcheck:
            lines.append("    healthcheck:")
            for key, value in service.healthcheck.items():
                if key == "test":
                    lines.append(f"      test: {value}")
                else:
                    lines.append(f"      {key}: {value}")

        if service.depends_on:
            lines.append("    depends_on:")
            for service_name, config in service.depends_on.items():
                lines.append(f"      {service_name}:")
                if isinstance(config, dict):
                    for key, value in config.items():
                        lines.append(f"        {key}: {value}")
                else:
                    lines.append(f"        condition: {config}")

        return lines

    def write_to_file(self, filepath: Path) -> None:
        """ファイルに書き込む

        Args:
            filepath: 書き込み先のファイルパス

        Example:
            >>> generator = DockerComposeGenerator()
            >>> generator.add_service(service).add_volume(volume)
            >>> generator.write_to_file(Path("docker-compose.yml"))
        """
        filepath.write_text(self.generate(), encoding="utf-8")
