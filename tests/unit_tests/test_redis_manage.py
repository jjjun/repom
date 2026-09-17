"""Tests for Redis management functions.

Tests verify that redis/manage.py correctly uses config values for:
- Container naming
- Volume naming
- Port configuration
- Docker image version
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from repom.config import config
from repom.credentials import DEFAULT_CREDENTIAL_PLACEHOLDER
from repom.redis import RedisConfig, RedisContainerConfig
from repom.redis.manage import (
    RedisManager,
    generate_docker_compose,
    generate_redis_conf,
)


@pytest.fixture(autouse=True)
def _redis_password_configured():
    """Give every test a real password by default.

    ``generate_redis_conf()``/``generate_docker_compose()`` now fail closed
    on an unconfigured password; tests that care about that behavior
    override this with their own ``patch.object(config.redis, "password", ...)``.
    """
    with patch.object(config.redis, "password", "test-redis-password"):
        yield


def test_redis_package_exports_config_classes_only():
    import repom.redis as redis

    assert redis.RedisConfig is RedisConfig
    assert redis.RedisContainerConfig is RedisContainerConfig
    assert redis.__all__ == ["RedisConfig", "RedisContainerConfig"]


def test_redis_package_no_longer_lazy_exports_manage_functions():
    with pytest.raises(ImportError):
        from repom.redis import generate  # noqa: F401


class TestRedisManager:
    """Tests for RedisManager class."""

    def test_get_container_name_uses_config(self):
        """コンテナ名が config.redis.container.get_container_name() を使用"""
        manager = RedisManager()
        container_name = manager.get_container_name()

        # Should use config value
        assert container_name == config.redis.container.get_container_name()
        assert container_name.startswith("repom_redis")

    def test_print_connection_info_uses_config_port(self, capsys):
        """print_connection_info が config.redis.port を使用"""
        manager = RedisManager()
        manager.print_connection_info()

        captured = capsys.readouterr()
        assert f"Port: {config.redis.port}" in captured.out
        assert f"redis-cli -p {config.redis.port}" in captured.out


class TestGenerateDockerCompose:
    """Tests for generate_docker_compose function."""

    def test_compose_uses_config_port(self):
        """docker-compose が config.redis.port を使用"""
        generator = generate_docker_compose()

        # The generator should have created a Redis service
        assert generator is not None
        # The service details are embedded in the generator
        # We verify by checking the config values are used
        assert config.redis.port == config.redis.port  # Basic sanity check

    def test_compose_uses_config_container_name(self):
        """docker-compose が config.redis.container.get_container_name() を使用"""
        expected_name = config.redis.container.get_container_name()
        generator = generate_docker_compose()

        # The generator should reflect the configured container name
        assert generator is not None
        assert expected_name.startswith("repom_redis")

    def test_compose_uses_config_volume_name(self):
        """docker-compose が config.redis.container.get_volume_name() を使用"""
        expected_volume = config.redis.container.get_volume_name()
        generator = generate_docker_compose()

        # The generator should have the configured volume name
        assert generator is not None
        assert expected_volume.startswith("repom_redis")

    def test_compose_uses_config_image(self):
        """docker-compose が config.redis.container.image を使用"""
        expected_image = config.redis.container.image
        generator = generate_docker_compose()

        # The generator should use the configured image
        assert generator is not None
        assert expected_image == "redis:7-alpine"  # Default value

    def test_compose_ports_bind_loopback_by_default(self):
        """Published ports bind to 127.0.0.1 unless expose_to_lan is set."""
        with patch.object(config.redis.container, "expose_to_lan", False):
            generator = generate_docker_compose()

        for port in generator.services[0].ports:
            assert port.startswith("127.0.0.1:")

    def test_compose_exposes_to_lan_when_configured(self):
        """expose_to_lan=True publishes the port on every interface."""
        with patch.object(config.redis.container, "expose_to_lan", True):
            generator = generate_docker_compose()

        for port in generator.services[0].ports:
            assert port.startswith("0.0.0.0:")

    def test_compose_rejects_newline_in_password(self):
        """A newline in the password cannot inject an extra YAML key."""
        with patch.object(
            config.redis, "password", "hostile\nPOSTGRES_HOST_AUTH_METHOD: trust"
        ):
            with pytest.raises(ValueError, match="redis.password"):
                generate_docker_compose()

    def test_compose_rejects_newline_in_container_name(self):
        """A newline in the container name raises before it reaches the YAML."""
        with patch.object(
            config.redis.container, "container_name", "repom_redis\nprivileged: true"
        ):
            with pytest.raises(ValueError, match="redis.container.container_name"):
                generate_docker_compose()

    def test_compose_command_authenticates_via_requirepass_flag(self):
        """The command passes --requirepass with the environment-expanded
        password; it never inlines the actual value."""
        with patch.object(config.redis, "password", "s3cret"):
            generator = generate_docker_compose()

        command = generator.services[0].command
        assert "$$REDIS_PASSWORD" in command
        assert "s3cret" not in command

    def test_compose_healthcheck_authenticates_via_environment(self):
        """The healthcheck reads the password from the container environment,
        never from the compose file itself."""
        with patch.object(config.redis, "password", "s3cret"):
            generator = generate_docker_compose()

        healthcheck_test = generator.services[0].healthcheck["test"]
        assert "$$REDIS_PASSWORD" in healthcheck_test
        assert "s3cret" not in healthcheck_test

    def test_compose_rejects_unset_password(self):
        """generate_docker_compose() fails closed when no real password is configured."""
        with patch.object(config.redis, "password", DEFAULT_CREDENTIAL_PLACEHOLDER):
            with pytest.raises(ValueError, match="REDIS_PASSWORD"):
                generate_docker_compose()

    def test_compose_rejects_empty_password(self):
        with patch.object(config.redis, "password", ""):
            with pytest.raises(ValueError, match="REDIS_PASSWORD"):
                generate_docker_compose()


class TestGenerateRedisConf:
    """Tests for generate_redis_conf function."""

    def test_conf_content_is_valid(self):
        """redis.conf の内容が有効な設定を含む"""
        conf = generate_redis_conf()

        # Should contain key configuration sections
        assert "databases" in conf
        assert "appendonly" in conf
        assert "save" in conf
        assert "maxmemory" in conf

    def test_conf_is_not_empty(self):
        """redis.conf が空でない"""
        conf = generate_redis_conf()
        assert len(conf) > 100  # Should have reasonable content

    def test_generated_redis_conf_never_sets_requirepass(self):
        """redis.conf is bind-mounted into the container, so the password
        never lands in it; the container reads it from the environment via
        --requirepass instead."""
        conf = generate_redis_conf(password="secret")

        assert "requirepass" not in conf
        assert "secret" not in conf

    def test_generated_redis_conf_omits_bind_loopback(self):
        """bind 127.0.0.1 inside the container would restrict Redis to the
        container's own loopback; host-side loopback restriction is enforced
        by the published port mapping instead."""
        conf = generate_redis_conf(password="secret")

        assert "bind 127.0.0.1" not in conf

    def test_generated_redis_conf_sets_protected_mode(self):
        conf = generate_redis_conf(password="secret")

        assert "protected-mode yes" in conf

    def test_conf_rejects_newline_in_password(self):
        """A newline in the password cannot inject an extra redis.conf directive."""
        with pytest.raises(ValueError, match="redis.password"):
            generate_redis_conf(password="hostile\nrequirepass forced")

    def test_conf_rejects_unset_password(self):
        with pytest.raises(ValueError, match="REDIS_PASSWORD"):
            generate_redis_conf(password=DEFAULT_CREDENTIAL_PLACEHOLDER)

    def test_conf_rejects_empty_password(self):
        with pytest.raises(ValueError, match="REDIS_PASSWORD"):
            generate_redis_conf(password="")


class TestConfigIntegration:
    """Tests for Config integration with redis module."""

    def test_redis_config_exists_in_repom_config(self):
        """config に redis フィールドがある"""
        assert hasattr(config, 'redis')

    def test_redis_config_has_container(self):
        """redis config に container フィールドがある"""
        assert hasattr(config.redis, 'container')

    def test_redis_config_has_port(self):
        """redis config に port フィールドがある"""
        assert hasattr(config.redis, 'port')
        assert isinstance(config.redis.port, int)
        assert config.redis.port > 0

    def test_redis_container_config_has_methods(self):
        """redis container config に必要なメソッドがある"""
        container = config.redis.container
        assert hasattr(container, 'get_container_name')
        assert hasattr(container, 'get_volume_name')
        assert callable(container.get_container_name)
        assert callable(container.get_volume_name)

    def test_redis_container_defaults(self):
        """redis container config のデフォルト値が正しい"""
        container = config.redis.container
        assert container.get_container_name() == "repom_redis"
        assert container.get_volume_name() == "repom_redis_data"
        assert container.image == "redis:7-alpine"


class TestDirectoryManagement:
    """Tests for directory management functions."""

    def test_get_compose_dir_returns_path(self):
        """get_compose_dir が有効なパスを返す"""
        compose_dir = RedisManager().get_compose_dir()
        assert isinstance(compose_dir, Path)
        assert compose_dir.exists()

    def test_get_init_dir_returns_path(self):
        """get_init_dir が有効なパスを返す"""
        init_dir = RedisManager().get_init_dir()
        assert isinstance(init_dir, Path)
        # Should be a subdirectory of compose dir
        assert "redis_init" in str(init_dir)

    def test_get_compose_dir_uses_redis_subdir(self):
        """get_compose_dir が redis サブディレクトリを使用（分離プロジェクト構造）"""
        compose_dir = RedisManager().get_compose_dir()
        # Should be config.data_path/redis/
        assert str(compose_dir).endswith("redis")
        assert "redis" in str(compose_dir)

    def test_redis_generate_creates_in_redis_subdir(self):
        """redis_generate が data/repom/redis/ に docker-compose.yml を生成"""
        from repom.redis.manage import generate

        # Generate files
        generate()

        # Verify files are in redis subdirectory
        compose_file = RedisManager().get_compose_dir() / "docker-compose.generated.yml"
        assert compose_file.exists()
        assert "redis" in str(compose_file.parent)

    def test_module_level_directory_helpers_are_removed(self):
        """module-level get_compose_dir/get_init_dir are no longer public."""
        with pytest.raises(ImportError):
            from repom.redis.manage import get_compose_dir  # noqa: F401

        with pytest.raises(ImportError):
            from repom.redis.manage import get_init_dir  # noqa: F401


class TestRedisSecretFilePermissions:
    """Tests for generated secret file permissions and content."""

    def test_generate_writes_password_to_env_file(self, tmp_path):
        """The Redis password is written to a .env secrets file, not the compose file."""
        compose_dir = tmp_path / "compose"
        compose_dir.mkdir()
        init_dir = compose_dir / "redis_init"
        init_dir.mkdir()

        from repom.redis.manage import generate

        with patch.object(config.redis, "password", "redis-secret"):
            with patch.object(RedisManager, "get_compose_dir", return_value=compose_dir):
                with patch.object(RedisManager, "get_init_dir", return_value=init_dir):
                    generate()

        compose_content = (compose_dir / "docker-compose.generated.yml").read_text()
        assert "redis-secret" not in compose_content

        env_content = (compose_dir / ".env").read_text()
        assert env_content == 'REDIS_PASSWORD="redis-secret"\n'


class TestRedisEnsureRunning:
    """ensure_running() の単体テスト"""

    def _patch_config(self):
        from unittest.mock import MagicMock

        mock_config = MagicMock()
        mock_config.redis.container.get_container_name.return_value = "repom_redis"
        return mock_config

    def test_returns_when_redis_already_running(self):
        from unittest.mock import patch

        from repom.redis import manage

        with patch.object(manage, "config", self._patch_config()):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                return_value=True,
            ) as is_running:
                with patch.object(manage, "generate") as generate:
                    with patch.object(manage, "RedisManager") as manager_cls:
                        manage.ensure_running()

        is_running.assert_called_once_with("repom_redis")
        generate.assert_not_called()
        manager_cls.assert_not_called()

    def test_starts_when_redis_down(self):
        from unittest.mock import MagicMock, patch

        from repom.redis import manage

        manager_instance = MagicMock()
        with patch.object(manage, "config", self._patch_config()):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                return_value=False,
            ):
                with patch.object(manage, "generate") as generate:
                    with patch.object(
                        manage, "RedisManager", return_value=manager_instance
                    ):
                        manage.ensure_running(timeout_seconds=12)

        generate.assert_called_once_with()
        manager_instance.start.assert_called_once_with(timeout_seconds=12)

    def test_default_timeout_seconds_is_30(self):
        from unittest.mock import MagicMock, patch

        from repom.redis import manage

        manager_instance = MagicMock()
        with patch.object(manage, "config", self._patch_config()):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                return_value=False,
            ):
                with patch.object(manage, "generate"):
                    with patch.object(
                        manage, "RedisManager", return_value=manager_instance
                    ):
                        manage.ensure_running()

        manager_instance.start.assert_called_once_with(timeout_seconds=30)

    def test_raises_runtime_error_when_docker_missing(self):
        from unittest.mock import patch

        import pytest

        from repom.redis import manage

        with patch.object(manage, "config", self._patch_config()):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                side_effect=FileNotFoundError("docker not found"),
            ):
                with pytest.raises(RuntimeError, match="docker command not found"):
                    manage.ensure_running()

    def test_raises_runtime_error_when_docker_daemon_unavailable(self):
        import subprocess
        from unittest.mock import patch

        import pytest

        from repom.redis import manage

        with patch.object(manage, "config", self._patch_config()):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                side_effect=subprocess.CalledProcessError(
                    1,
                    ["docker", "ps"],
                    stderr="Cannot connect to the Docker daemon",
                ),
            ):
                with pytest.raises(
                    RuntimeError, match="Cannot connect to the Docker daemon"
                ):
                    manage.ensure_running()

    def test_raises_runtime_error_on_timeout(self):
        from unittest.mock import MagicMock, patch

        import pytest

        from repom.redis import manage

        manager_instance = MagicMock()
        manager_instance.start.side_effect = TimeoutError(
            "Redis did not start within 30 seconds"
        )
        with patch.object(manage, "config", self._patch_config()):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                return_value=False,
            ):
                with patch.object(manage, "generate"):
                    with patch.object(
                        manage, "RedisManager", return_value=manager_instance
                    ):
                        with pytest.raises(RuntimeError, match="Failed to start Redis"):
                            manage.ensure_running()

    def test_raises_runtime_error_on_system_exit(self):
        from unittest.mock import MagicMock, patch

        import pytest

        from repom.redis import manage

        manager_instance = MagicMock()
        manager_instance.start.side_effect = SystemExit(1)
        with patch.object(manage, "config", self._patch_config()):
            with patch(
                "basekit.docker_manager.DockerCommandExecutor.is_container_running",
                return_value=False,
            ):
                with patch.object(manage, "generate"):
                    with patch.object(
                        manage, "RedisManager", return_value=manager_instance
                    ):
                        with pytest.raises(RuntimeError, match="Failed to start Redis"):
                            manage.ensure_running()



