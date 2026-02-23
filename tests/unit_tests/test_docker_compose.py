"""repom._.docker_compose の単体テスト"""

import pytest
from pathlib import Path
from repom._.docker_compose import DockerComposeGenerator, DockerService, DockerVolume


class TestDockerService:
    """DockerService のテスト"""

    def test_create_minimal_service(self):
        """最小限のサービスを作成"""
        service = DockerService(
            name="postgres",
            image="postgres:16-alpine",
            container_name="test_postgres"
        )

        assert service.name == "postgres"
        assert service.image == "postgres:16-alpine"
        assert service.container_name == "test_postgres"
        assert service.ports == []
        assert service.environment == {}
        assert service.volumes == []
        assert service.healthcheck is None

    def test_create_full_service(self):
        """すべての設定を持つサービスを作成"""
        service = DockerService(
            name="postgres",
            image="postgres:16-alpine",
            container_name="test_postgres",
            ports=["5432:5432"],
            environment={"POSTGRES_USER": "user", "POSTGRES_PASSWORD": "pass"},
            volumes=["postgres_data:/var/lib/postgresql/data"],
            healthcheck={
                "test": '["CMD-SHELL", "pg_isready -U user"]',
                "interval": "5s",
                "timeout": "5s",
                "retries": 5
            }
        )

        assert service.name == "postgres"
        assert service.ports == ["5432:5432"]
        assert service.environment == {"POSTGRES_USER": "user", "POSTGRES_PASSWORD": "pass"}
        assert service.volumes == ["postgres_data:/var/lib/postgresql/data"]
        assert service.healthcheck["test"] == '["CMD-SHELL", "pg_isready -U user"]'


class TestDockerVolume:
    """DockerVolume のテスト"""

    def test_create_default_volume(self):
        """デフォルト設定でボリュームを作成"""
        volume = DockerVolume(name="postgres_data")

        assert volume.name == "postgres_data"
        assert volume.driver == "local"

    def test_create_custom_driver_volume(self):
        """カスタムドライバーでボリュームを作成"""
        volume = DockerVolume(name="nfs_data", driver="nfs")

        assert volume.name == "nfs_data"
        assert volume.driver == "nfs"


class TestDockerComposeGenerator:
    """DockerComposeGenerator のテスト"""

    def test_create_empty_generator(self):
        """空の生成器を作成"""
        generator = DockerComposeGenerator()

        assert generator.version == "3.8"
        assert generator.services == []
        assert generator.volumes == []

    def test_create_custom_version_generator(self):
        """カスタムバージョンで生成器を作成"""
        generator = DockerComposeGenerator(version="3.9")

        assert generator.version == "3.9"

    def test_add_service(self):
        """サービスを追加"""
        generator = DockerComposeGenerator()
        service = DockerService(
            name="postgres",
            image="postgres:16-alpine",
            container_name="test_postgres"
        )

        result = generator.add_service(service)

        assert result is generator  # メソッドチェーン確認
        assert len(generator.services) == 1
        assert generator.services[0] == service

    def test_add_volume(self):
        """ボリュームを追加"""
        generator = DockerComposeGenerator()
        volume = DockerVolume(name="postgres_data")

        result = generator.add_volume(volume)

        assert result is generator  # メソッドチェーン確認
        assert len(generator.volumes) == 1
        assert generator.volumes[0] == volume

    def test_method_chaining(self):
        """メソッドチェーンでサービスとボリュームを追加"""
        generator = DockerComposeGenerator()
        service = DockerService(name="postgres", image="postgres:16-alpine", container_name="test")
        volume = DockerVolume(name="postgres_data")

        generator.add_service(service).add_volume(volume)

        assert len(generator.services) == 1
        assert len(generator.volumes) == 1

    def test_generate_minimal_compose(self):
        """最小限の docker-compose.yml を生成"""
        generator = DockerComposeGenerator()
        service = DockerService(
            name="postgres",
            image="postgres:16-alpine",
            container_name="test_postgres"
        )
        generator.add_service(service)

        yaml_content = generator.generate()

        assert "version: '3.8'" in yaml_content
        assert "services:" in yaml_content
        assert "  postgres:" in yaml_content
        assert "    image: postgres:16-alpine" in yaml_content
        assert "    container_name: test_postgres" in yaml_content

    def test_generate_compose_with_environment(self):
        """環境変数を含む docker-compose.yml を生成"""
        generator = DockerComposeGenerator()
        service = DockerService(
            name="postgres",
            image="postgres:16-alpine",
            container_name="test_postgres",
            environment={"POSTGRES_USER": "user", "POSTGRES_PASSWORD": "pass"}
        )
        generator.add_service(service)

        yaml_content = generator.generate()

        assert "    environment:" in yaml_content
        assert "      POSTGRES_USER: user" in yaml_content
        assert "      POSTGRES_PASSWORD: pass" in yaml_content

    def test_generate_compose_with_ports(self):
        """ポートマッピングを含む docker-compose.yml を生成"""
        generator = DockerComposeGenerator()
        service = DockerService(
            name="postgres",
            image="postgres:16-alpine",
            container_name="test_postgres",
            ports=["5432:5432"]
        )
        generator.add_service(service)

        yaml_content = generator.generate()

        assert "    ports:" in yaml_content
        assert '      - "5432:5432"' in yaml_content

    def test_generate_compose_with_volumes(self):
        """ボリュームを含む docker-compose.yml を生成"""
        generator = DockerComposeGenerator()
        service = DockerService(
            name="postgres",
            image="postgres:16-alpine",
            container_name="test_postgres",
            volumes=["postgres_data:/var/lib/postgresql/data"]
        )
        volume = DockerVolume(name="postgres_data")
        generator.add_service(service).add_volume(volume)

        yaml_content = generator.generate()

        assert "    volumes:" in yaml_content
        assert "      - postgres_data:/var/lib/postgresql/data" in yaml_content
        assert "volumes:" in yaml_content
        assert "  postgres_data:" in yaml_content

    def test_generate_compose_with_healthcheck(self):
        """ヘルスチェックを含む docker-compose.yml を生成"""
        generator = DockerComposeGenerator()
        service = DockerService(
            name="postgres",
            image="postgres:16-alpine",
            container_name="test_postgres",
            healthcheck={
                "test": '["CMD-SHELL", "pg_isready -U user"]',
                "interval": "5s",
                "timeout": "5s",
                "retries": 5
            }
        )
        generator.add_service(service)

        yaml_content = generator.generate()

        assert "    healthcheck:" in yaml_content
        assert '      test: ["CMD-SHELL", "pg_isready -U user"]' in yaml_content
        assert "      interval: 5s" in yaml_content
        assert "      timeout: 5s" in yaml_content
        assert "      retries: 5" in yaml_content

    def test_generate_full_compose(self):
        """すべての設定を含む docker-compose.yml を生成"""
        generator = DockerComposeGenerator(version="3.9")

        # PostgreSQL サービス
        postgres_service = DockerService(
            name="postgres",
            image="postgres:16-alpine",
            container_name="repom_postgres",
            environment={"POSTGRES_USER": "repom", "POSTGRES_PASSWORD": "repom_dev", "POSTGRES_DB": "repom_dev"},
            ports=["5432:5432"],
            volumes=["postgres_data:/var/lib/postgresql/data"],
            healthcheck={
                "test": '["CMD-SHELL", "pg_isready -U repom"]',
                "interval": "5s",
                "timeout": "5s",
                "retries": 5
            }
        )
        postgres_volume = DockerVolume(name="postgres_data")

        generator.add_service(postgres_service).add_volume(postgres_volume)

        yaml_content = generator.generate()

        # バージョン確認
        assert "version: '3.9'" in yaml_content

        # サービス確認
        assert "services:" in yaml_content
        assert "  postgres:" in yaml_content
        assert "    image: postgres:16-alpine" in yaml_content
        assert "    container_name: repom_postgres" in yaml_content

        # 環境変数確認
        assert "    environment:" in yaml_content
        assert "      POSTGRES_USER: repom" in yaml_content
        assert "      POSTGRES_PASSWORD: repom_dev" in yaml_content
        assert "      POSTGRES_DB: repom_dev" in yaml_content

        # ポート確認
        assert "    ports:" in yaml_content
        assert '      - "5432:5432"' in yaml_content

        # ボリューム確認
        assert "    volumes:" in yaml_content
        assert "      - postgres_data:/var/lib/postgresql/data" in yaml_content
        assert "volumes:" in yaml_content
        assert "  postgres_data:" in yaml_content

        # ヘルスチェック確認
        assert "    healthcheck:" in yaml_content

    def test_write_to_file(self, tmp_path):
        """ファイルに書き込む"""
        generator = DockerComposeGenerator()
        service = DockerService(
            name="postgres",
            image="postgres:16-alpine",
            container_name="test_postgres"
        )
        generator.add_service(service)

        output_path = tmp_path / "docker-compose.yml"
        generator.write_to_file(output_path)

        assert output_path.exists()

        content = output_path.read_text(encoding="utf-8")
        assert "version: '3.8'" in content
        assert "  postgres:" in content

    def test_multiple_services(self):
        """複数のサービスを含む docker-compose.yml を生成"""
        generator = DockerComposeGenerator()

        postgres = DockerService(
            name="postgres",
            image="postgres:16-alpine",
            container_name="test_postgres",
            ports=["5432:5432"]
        )

        redis = DockerService(
            name="redis",
            image="redis:7-alpine",
            container_name="test_redis",
            ports=["6379:6379"]
        )

        generator.add_service(postgres).add_service(redis)

        yaml_content = generator.generate()

        assert "  postgres:" in yaml_content
        assert "  redis:" in yaml_content
        assert '      - "5432:5432"' in yaml_content
        assert '      - "6379:6379"' in yaml_content

    def test_custom_driver_volume(self):
        """カスタムドライバーのボリュームを含む docker-compose.yml を生成"""
        generator = DockerComposeGenerator()

        service = DockerService(
            name="app",
            image="myapp:latest",
            container_name="test_app",
            volumes=["nfs_data:/data"]
        )
        volume = DockerVolume(name="nfs_data", driver="nfs")

        generator.add_service(service).add_volume(volume)

        yaml_content = generator.generate()

        assert "  nfs_data:" in yaml_content
        assert "    driver: nfs" in yaml_content

    def test_generate_compose_with_depends_on(self):
        """depends_on を含む docker-compose.yml を生成"""
        generator = DockerComposeGenerator()

        # PostgreSQL サービス（healthcheck 付き）
        postgres_service = DockerService(
            name="postgres",
            image="postgres:16-alpine",
            container_name="test_postgres",
            healthcheck={
                "test": '["CMD-SHELL", "pg_isready -U postgres"]',
                "interval": "5s",
                "timeout": "5s",
                "retries": 5
            }
        )

        # pgAdmin サービス（PostgreSQL に依存）
        pgadmin_service = DockerService(
            name="pgadmin",
            image="dpage/pgadmin4:latest",
            container_name="test_pgadmin",
            depends_on={"postgres": {"condition": "service_healthy"}}
        )

        generator.add_service(postgres_service).add_service(pgadmin_service)
        yaml_content = generator.generate()

        # depends_on が YAML に含まれるか確認
        assert "    depends_on:" in yaml_content
        assert "      postgres:" in yaml_content
        assert "        condition: service_healthy" in yaml_content

    def test_depends_on_with_multiple_conditions(self):
        """複数の条件を持つ depends_on"""
        generator = DockerComposeGenerator()

        service = DockerService(
            name="app",
            image="app:latest",
            container_name="test_app",
            depends_on={
                "postgres": {"condition": "service_healthy"},
                "redis": {"condition": "service_started"}
            }
        )

        generator.add_service(service)
        yaml_content = generator.generate()

        assert "    depends_on:" in yaml_content
        assert "      postgres:" in yaml_content
        assert "        condition: service_healthy" in yaml_content
        assert "      redis:" in yaml_content
        assert "        condition: service_started" in yaml_content
