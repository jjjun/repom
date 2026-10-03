"""Tests for Redis management functions.

Tests verify that redis/manage.py correctly uses config values for:
- Container naming
- Volume naming
- Port configuration
- Docker image version
"""

import os
from pathlib import Path
import stat
from unittest.mock import MagicMock, patch

import pytest
from basekit.docker_manager import DockerCommandExecutor

from repom.config import config
from repom.credentials import DEFAULT_CREDENTIAL_PLACEHOLDER
from repom.redis import RedisConfig, RedisContainerConfig
from repom.redis import manage
from repom.redis.manage import (
    RedisManager,
    generate_docker_compose,
    generate_redis_conf,
)


@pytest.fixture(autouse=True)
def _redis_password_configured(tmp_path, monkeypatch):
    """Give every test a real password by default.

    ``generate_redis_conf()``/``generate_docker_compose()`` now fail closed
    on an unconfigured password; tests that care about that behavior
    override this with their own ``patch.object(config.redis, "password", ...)``.
    """
    monkeypatch.setattr(config, "root_path", str(tmp_path))
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
        assert manager.config is config


class TestRedisManagerConnectionInfo:
    def test_print_connection_info_uses_config_port(self, capsys):
        """print_connection_info が config.redis.port を使用"""
        manager = RedisManager()
        with patch.object(config.redis.container, "host_port", None):
            manager.print_connection_info()

        captured = capsys.readouterr()
        assert "Redis Connection" in captured.out
        assert "127.0.0.1" in captured.out
        assert f"Port: {config.redis.port}" in captured.out
        assert f"redis-cli -p {config.redis.port}" in captured.out


class TestRedisManagerWaitForService:
    """Tests for Redis-specific readiness checks."""

    @pytest.fixture(autouse=True)
    def _patch_readiness_sleep(self):
        with patch("basekit.docker_manager.time.sleep") as sleep:
            yield sleep

    def test_wait_for_service_immediate_success(self, _patch_readiness_sleep):
        with patch("repom.redis.manage.subprocess.run") as run:
            run.return_value = MagicMock(returncode=0, stdout="PONG\n")

            RedisManager().wait_for_service(max_retries=2)

        assert run.call_count == 1
        _patch_readiness_sleep.assert_not_called()

    def test_wait_for_service_retries_until_ready(self, _patch_readiness_sleep):
        with patch("repom.redis.manage.subprocess.run") as run:
            run.side_effect = [
                MagicMock(returncode=1, stdout=""),
                MagicMock(returncode=1, stdout=""),
                MagicMock(returncode=0, stdout="PONG\n"),
            ]

            RedisManager().wait_for_service(max_retries=3)

        assert run.call_count == 3
        assert _patch_readiness_sleep.call_count == 2

    def test_wait_for_service_times_out(self, _patch_readiness_sleep):
        with patch("repom.redis.manage.subprocess.run") as run:
            run.return_value = MagicMock(returncode=1, stdout="")

            with pytest.raises(TimeoutError):
                RedisManager().wait_for_service(max_retries=1)

        assert _patch_readiness_sleep.call_count == 1

    def test_wait_for_service_handles_subprocess_exception(
        self, _patch_readiness_sleep
    ):
        with patch("repom.redis.manage.subprocess.run") as run:
            run.side_effect = OSError("Docker is unavailable")

            with pytest.raises(TimeoutError):
                RedisManager().wait_for_service(max_retries=1)

        run.assert_called_once()
        _patch_readiness_sleep.assert_called_once_with(1)

    def test_wait_for_service_never_places_password_in_argv(
        self, _patch_readiness_sleep
    ):
        with patch.object(config.redis, "password", "sentinel-secret"):
            with patch("repom.redis.manage.subprocess.run") as run:
                run.side_effect = [
                    MagicMock(returncode=1, stdout="", stderr="not ready"),
                    MagicMock(returncode=0, stdout="PONG\n"),
                ]

                RedisManager().wait_for_service(max_retries=2)

        assert run.call_count == 2
        for call in run.call_args_list:
            assert "sentinel-secret" not in " ".join(call.args[0])
        _patch_readiness_sleep.assert_called_once_with(1)

    def test_wait_for_service_treats_noauth_response_as_ready(
        self, _patch_readiness_sleep
    ):
        with patch.object(config.redis, "password", "secret"):
            with patch("repom.redis.manage.subprocess.run") as run:
                run.return_value = MagicMock(
                    returncode=1,
                    stdout="",
                    stderr="NOAUTH Authentication required.",
                )

                RedisManager().wait_for_service(max_retries=1)

        run.assert_called_once()
        _patch_readiness_sleep.assert_not_called()


class TestGenerateDockerCompose:
    """Tests for generate_docker_compose function."""

    def test_compose_uses_config_port(self):
        """docker-compose が config.redis.port を使用"""
        generator = generate_docker_compose()

        service = generator.services[0]
        assert service.ports == [f"127.0.0.1:{config.redis.published_port}:6379"]

    def test_compose_uses_config_container_name(self):
        """docker-compose が config.redis.container.get_container_name() を使用"""
        expected_name = config.redis.container.get_container_name()
        generator = generate_docker_compose()

        assert generator.services[0].container_name == expected_name

    def test_compose_uses_config_volume_name(self):
        """docker-compose が config.redis.container.get_volume_name() を使用"""
        expected_volume = config.redis.container.get_volume_name()
        generator = generate_docker_compose()

        assert generator.services[0].volumes[0] == f"{expected_volume}:/data"

    def test_compose_uses_config_image(self):
        """docker-compose が config.redis.container.image を使用"""
        expected_image = config.redis.container.image
        generator = generate_docker_compose()

        assert generator.services[0].image == expected_image

    def test_compose_ports_bind_loopback_by_default(self):
        """Published ports bind to 127.0.0.1 unless expose_to_lan is set."""
        with (
            patch.object(config.redis.container, "host_port", None),
            patch.object(config.redis.container, "expose_to_lan", False),
        ):
            generator = generate_docker_compose()

        assert generator.services[0].ports == [
            f"127.0.0.1:{config.redis.port}:6379"
        ]

    def test_compose_exposes_to_lan_when_configured(self):
        """expose_to_lan=True publishes the port on every interface."""
        with (
            patch.object(config.redis.container, "host_port", 6390),
            patch.object(config.redis.container, "expose_to_lan", True),
        ):
            generator = generate_docker_compose()

        assert generator.services[0].ports == ["0.0.0.0:6390:6379"]

    def test_compose_uses_host_port_when_configured(self):
        with (
            patch.object(config.redis, "port", 6381),
            patch.object(config.redis.container, "host_port", 6390),
        ):
            generator = generate_docker_compose()

        assert generator.services[0].ports == ["127.0.0.1:6390:6379"]

    def test_generate_writes_host_port_override_with_temporary_data_path(
        self, tmp_path, monkeypatch
    ):
        from repom.config import RepomConfig
        from repom.config_hooks.redis import apply_redis_env_overrides
        from repom.redis import manage

        monkeypatch.setenv("REDIS_PORT", "6381")
        monkeypatch.setenv("REDIS_HOST_PORT", "6390")
        monkeypatch.setenv("REDIS_PASSWORD", "test-redis-password")
        test_config = RepomConfig(root_path=str(tmp_path))
        apply_redis_env_overrides(test_config)
        monkeypatch.setattr(manage, "config", test_config)

        manage.generate()

        compose_path = (
            Path(test_config.data_path) / "redis" / manage.COMPOSE_FILENAME
        )
        assert "127.0.0.1:6390:6379" in compose_path.read_text(encoding="utf-8")

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

    @pytest.mark.parametrize(
        ("attribute", "value", "field_name"),
        [
            ("image", "redis:7\nservices:", "redis.container.image"),
            ("image", "-redis", "redis.container.image"),
            ("volume_name", "host:/data", "redis.container.volume_name"),
            ("volume_name", "host/path", "redis.container.volume_name"),
            ("container_name", "-redis", "redis.container.container_name"),
        ],
    )
    def test_compose_rejects_unsafe_generated_names_and_images(
        self, attribute, value, field_name
    ):
        with patch.object(config.redis.container, attribute, value):
            with pytest.raises(ValueError, match=field_name):
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

        service = generator.services[0]
        healthcheck_test = service.healthcheck["test"]
        assert "redis-cli ping" in healthcheck_test
        assert "-a" not in healthcheck_test
        assert "REDIS_PASSWORD" not in healthcheck_test
        assert (
            service.environment["REDISCLI_AUTH"]
            == service.environment["REDIS_PASSWORD"]
        )
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

        assert "databases 16" in conf
        assert "appendonly yes" in conf
        assert "save 900 1" in conf
        assert "maxmemory 256mb" in conf

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


class TestDirectoryManagement:
    """Tests for directory management functions."""

    def test_redis_generate_creates_in_redis_subdir(self, tmp_path):
        """redis_generate が data/repom/redis/ に docker-compose.yml を生成"""
        from repom.redis.manage import generate

        compose_dir = tmp_path / "redis"
        compose_dir.mkdir()
        init_dir = compose_dir / "redis_init"
        init_dir.mkdir()

        # Generate files
        with patch.object(RedisManager, "get_compose_dir", return_value=compose_dir):
            with patch.object(RedisManager, "get_init_dir", return_value=init_dir):
                generate()

        # Verify files are in redis subdirectory
        compose_file = compose_dir / "docker-compose.generated.yml"
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

    def test_generate_refuses_changed_password_and_force_keeps_backup(self, tmp_path):
        compose_dir = tmp_path / "compose"
        compose_dir.mkdir()
        init_dir = compose_dir / "redis_init"
        init_dir.mkdir()
        env_file = compose_dir / ".env"
        original_env = 'REDIS_PASSWORD="old-redis-secret"\n'
        env_file.write_text(original_env, encoding="utf-8")

        from repom.redis.manage import generate

        with patch.object(config.redis, "password", "new-redis-secret"):
            with patch.object(RedisManager, "get_compose_dir", return_value=compose_dir):
                with patch.object(RedisManager, "get_init_dir", return_value=init_dir):
                    with pytest.raises(ValueError) as excinfo:
                        generate()

                    assert "redis_rotate_password" in str(excinfo.value)
                    assert "new-redis-secret" not in str(excinfo.value)
                    assert env_file.read_text(encoding="utf-8") == original_env
                    assert not (compose_dir / "docker-compose.generated.yml").exists()

                    generate(overwrite_secrets=True)

        assert env_file.read_text(encoding="utf-8") == 'REDIS_PASSWORD="new-redis-secret"\n'
        assert (compose_dir / ".env.bak").read_text(encoding="utf-8") == original_env
        if os.name == "posix":
            assert stat.S_IMODE((compose_dir / ".env.bak").stat().st_mode) == 0o600


class TestRedisEnsureRunning:
    """ensure_running() の単体テスト"""

    def _patch_config(self):
        from unittest.mock import MagicMock

        mock_config = MagicMock()
        mock_config.data_path = "/repom-test-data-does-not-exist"
        mock_config.redis.container.get_container_name.return_value = "repom_redis"
        return mock_config

    def test_uses_existing_generated_files_when_redis_is_down(self, tmp_path):
        from unittest.mock import MagicMock, patch

        from repom.redis import manage

        mock_config = self._patch_config()
        compose_dir = tmp_path / "redis"
        compose_dir.mkdir()
        (compose_dir / manage.COMPOSE_FILENAME).write_text("services: {}\n")
        (compose_dir / ".env").write_text('REDIS_PASSWORD="saved-secret"\n')
        manager_instance = MagicMock()
        manager_instance.get_compose_dir.return_value = compose_dir

        with patch.object(manage, "config", mock_config):
            with patch(
                "repom.docker_service.is_container_running",
                return_value=False,
            ):
                with patch.object(manage, "_prepare_auto_start") as prepare:
                    with patch.object(manage, "RedisManager", return_value=manager_instance):
                        manage.ensure_running()

        prepare.assert_called_once_with()
        manager_instance.get_compose_dir.assert_called_once_with()
        manager_instance.start.assert_called_once_with(timeout_seconds=30)

    def test_returns_when_redis_already_running(self):
        from unittest.mock import patch

        from repom.redis import manage

        with patch.object(manage, "config", self._patch_config()):
            with patch(
                "repom.docker_service.is_container_running",
                return_value=True,
            ) as is_running:
                with patch.object(manage, "generate") as generate:
                    with patch.object(manage, "RedisManager") as manager_cls:
                        manage.ensure_running()

        is_running.assert_called_once_with("repom_redis")
        generate.assert_not_called()
        manager_cls.assert_not_called()

    def test_starts_when_redis_down(self, tmp_path):
        from unittest.mock import MagicMock, patch

        from repom.redis import manage

        manager_instance = MagicMock()
        manager_instance.get_compose_dir.return_value = tmp_path / "redis"
        with patch.object(manage, "config", self._patch_config()):
            with patch(
                "repom.docker_service.is_container_running",
                return_value=False,
            ):
                with patch.object(manage, "generate") as generate:
                    with patch.object(
                        manage, "RedisManager", return_value=manager_instance
                    ):
                        manage.ensure_running(timeout_seconds=12)

        generate.assert_called_once_with()
        manager_instance.start.assert_called_once_with(timeout_seconds=12)

    def test_default_timeout_seconds_is_30(self, tmp_path):
        from unittest.mock import MagicMock, patch

        from repom.redis import manage

        manager_instance = MagicMock()
        manager_instance.get_compose_dir.return_value = tmp_path / "redis"
        with patch.object(manage, "config", self._patch_config()):
            with patch(
                "repom.docker_service.is_container_running",
                return_value=False,
            ):
                with patch.object(manage, "generate"):
                    with patch.object(
                        manage, "RedisManager", return_value=manager_instance
                    ):
                        manage.ensure_running()

        manager_instance.start.assert_called_once_with(timeout_seconds=30)

class TestRedisGenerationCLI:
    def test_force_regenerate_flag_is_forwarded_to_generate(self, monkeypatch):
        import sys

        from repom.redis import manage

        monkeypatch.setattr(sys, "argv", ["redis_generate", "--force-regenerate"])
        with patch.object(manage, "generate") as generate:
            manage.main_generate()

        generate.assert_called_once_with(overwrite_secrets=True)

    def test_force_regenerate_flag_is_forwarded_to_start(self, monkeypatch):
        import sys

        from repom.redis import manage

        monkeypatch.setattr(sys, "argv", ["redis_start", "--force-regenerate"])
        with patch.object(manage, "start") as start:
            manage.main_start()

        start.assert_called_once_with(overwrite_secrets=True)


@pytest.mark.parametrize(
    ("entrypoint", "compose_command"),
    [
        pytest.param(manage.start, "up -d", id="start"),
        pytest.param(manage.stop, "stop", id="stop"),
        pytest.param(manage.remove, "down -v", id="remove"),
    ],
)
def test_lifecycle_entrypoints_run_expected_compose_command(
    entrypoint, compose_command, monkeypatch, tmp_path
):
    compose_file = tmp_path / "docker-compose.generated.yml"
    compose_file.write_text("services: {}\n", encoding="utf-8")
    monkeypatch.setattr(
        RedisManager, "get_compose_file_path", lambda self: compose_file
    )
    run_compose = MagicMock()
    monkeypatch.setattr(DockerCommandExecutor, "run_docker_compose", run_compose)

    if entrypoint is manage.start:
        generate = MagicMock()
        monkeypatch.setattr(manage, "generate", generate)
        monkeypatch.setattr(
            RedisManager, "wait_for_service", lambda self, max_retries: None
        )
    else:
        monkeypatch.setattr(manage, "_write_secret_free_artifacts", MagicMock())

    entrypoint()

    if entrypoint is manage.start:
        generate.assert_called_once_with(overwrite_secrets=False)
    run_compose.assert_called_once_with(
        compose_command,
        compose_file,
        cwd=compose_file.parent,
        project_name=RedisManager().get_container_name(),
    )


class TestRedisAutoStartArtifactRefresh:
    def _make_config(self, tmp_path, *, name, port, volume, password):
        from types import SimpleNamespace

        return SimpleNamespace(
            data_path=tmp_path,
            redis=RedisConfig(
                password=password,
                container=RedisContainerConfig(
                    container_name=name,
                    host_port=port,
                    volume_name=volume,
                ),
            ),
        )

    def _make_manager(self, tmp_path):
        compose_dir = tmp_path / "redis"
        init_dir = tmp_path / "redis_init"
        compose_dir.mkdir()
        init_dir.mkdir()
        manager = MagicMock()
        manager.get_compose_dir.return_value = compose_dir
        manager.get_init_dir.return_value = init_dir
        return manager, compose_dir, init_dir

    def test_missing_env_runs_full_generation(self, tmp_path):
        manager, compose_dir, _ = self._make_manager(tmp_path)
        current_config = self._make_config(
            tmp_path,
            name="redis_current",
            port=26379,
            volume="redis_current_data",
            password="configured-secret",
        )
        with patch.object(manage, "config", current_config):
            with patch.object(manage, "RedisManager", return_value=manager):
                with patch("repom.docker_service.is_container_running", return_value=False):
                    manage.ensure_running()

        env_path = compose_dir / ".env"
        assert env_path.read_text(encoding="utf-8") == (
            'REDIS_PASSWORD="configured-secret"\n'
        )
        assert "redis_current" in (
            compose_dir / manage.COMPOSE_FILENAME
        ).read_text(encoding="utf-8")
        manager.start.assert_called_once_with(timeout_seconds=30)

    def test_auto_start_rewrites_for_current_container_and_reuses_env(
        self, tmp_path
    ):
        manager, compose_dir, init_dir = self._make_manager(tmp_path)
        config_a = self._make_config(
            tmp_path,
            name="redis_a",
            port=26379,
            volume="redis_a_data",
            password="saved-secret",
        )
        config_b = self._make_config(
            tmp_path,
            name="redis_b",
            port=26380,
            volume="redis_b_data",
            password=DEFAULT_CREDENTIAL_PLACEHOLDER,
        )
        with patch.object(manage, "config", config_a):
            with patch.object(manage, "RedisManager", return_value=manager):
                manage.generate()

        env_path = compose_dir / ".env"
        original_env = env_path.read_bytes()
        compose_file = compose_dir / manage.COMPOSE_FILENAME

        def assert_built_for_b(*, timeout_seconds):
            compose = compose_file.read_text(encoding="utf-8")
            assert "redis_b" in compose
            assert "26380:6379" in compose
            assert "redis_b_data:/data" in compose
            assert "redis_a" not in compose
            assert "redis_a_data" not in compose

        manager.start.side_effect = assert_built_for_b
        with patch.object(manage, "config", config_b):
            with patch.object(manage, "RedisManager", return_value=manager):
                with patch("repom.docker_service.is_container_running", return_value=False):
                    manage.ensure_running()

        manager.start.assert_called_once_with(timeout_seconds=30)
        assert env_path.read_bytes() == original_env
        assert not (compose_dir / ".env.bak").exists()
        assert (init_dir / "redis.conf").is_file()

    def test_auto_start_refuses_changed_secret_before_writing_files(self, tmp_path):
        manager, compose_dir, _ = self._make_manager(tmp_path)
        config_a = self._make_config(
            tmp_path,
            name="redis_a",
            port=26379,
            volume="redis_a_data",
            password="saved-secret",
        )
        with patch.object(manage, "config", config_a):
            with patch.object(manage, "RedisManager", return_value=manager):
                manage.generate()

        env_path = compose_dir / ".env"
        compose_file = compose_dir / manage.COMPOSE_FILENAME
        original_env = env_path.read_bytes()
        original_compose = compose_file.read_bytes()
        config_b = self._make_config(
            tmp_path,
            name="redis_b",
            port=26380,
            volume="redis_b_data",
            password="different-secret",
        )
        with patch.object(manage, "config", config_b):
            with patch.object(manage, "RedisManager", return_value=manager):
                with patch("repom.docker_service.is_container_running", return_value=False):
                    with pytest.raises(RuntimeError) as excinfo:
                        manage.ensure_running()

        message = str(excinfo.value)
        assert str(env_path) in message
        assert "redis_rotate_password" in message
        assert "redis_generate --force-regenerate" in message
        assert "saved-secret" not in message
        assert "different-secret" not in message
        assert env_path.read_bytes() == original_env
        assert compose_file.read_bytes() == original_compose
        assert not (compose_dir / ".env.bak").exists()
        manager.start.assert_not_called()

    def test_auto_start_reports_path_for_invalid_stored_env_without_writing(
        self, tmp_path
    ):
        manager, compose_dir, init_dir = self._make_manager(tmp_path)
        env_path = compose_dir / ".env"
        env_path.write_text("REDIS_PASSWORD=x\n", encoding="utf-8")
        compose_file = compose_dir / manage.COMPOSE_FILENAME
        compose_file.write_text("existing compose\n", encoding="utf-8")
        redis_conf = init_dir / "redis.conf"
        redis_conf.write_text("existing config\n", encoding="utf-8")
        current_config = self._make_config(
            tmp_path,
            name="redis_current",
            port=26379,
            volume="redis_current_data",
            password="configured-secret",
        )

        with patch.object(manage, "config", current_config):
            with patch.object(manage, "RedisManager", return_value=manager):
                with patch("repom.docker_service.is_container_running", return_value=False):
                    with pytest.raises(RuntimeError) as excinfo:
                        manage.ensure_running()

        message = str(excinfo.value)
        assert str(env_path) in message
        assert "redis_generate --force-regenerate" in message
        assert "REDIS_PASSWORD=x" not in message
        assert env_path.read_text(encoding="utf-8") == "REDIS_PASSWORD=x\n"
        assert compose_file.read_text(encoding="utf-8") == "existing compose\n"
        assert redis_conf.read_text(encoding="utf-8") == "existing config\n"
        manager.start.assert_not_called()

    @pytest.mark.parametrize("entrypoint", [manage.stop, manage.remove])
    def test_stop_and_remove_refresh_compose_before_lifecycle_call(
        self, entrypoint, tmp_path
    ):
        manager, compose_dir, _ = self._make_manager(tmp_path)
        compose_file = compose_dir / manage.COMPOSE_FILENAME
        compose_file.write_text("container_name: redis_a\n", encoding="utf-8")
        config_b = self._make_config(
            tmp_path,
            name="redis_b",
            port=26380,
            volume="redis_b_data",
            password=DEFAULT_CREDENTIAL_PLACEHOLDER,
        )

        def assert_current_compose():
            compose = compose_file.read_text(encoding="utf-8")
            assert "redis_b" in compose
            assert "redis_a" not in compose

        lifecycle_method = "stop" if entrypoint is manage.stop else "remove"
        getattr(manager, lifecycle_method).side_effect = assert_current_compose
        with patch.object(manage, "config", config_b):
            with patch.object(manage, "RedisManager", return_value=manager):
                entrypoint()
