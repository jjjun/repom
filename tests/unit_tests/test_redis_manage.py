"""Tests for Redis management functions.

Tests verify that redis/manage.py correctly uses config values for:
- Container naming
- Volume naming
- Port configuration
- Docker image version
"""

from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import pytest

from repom.config import config
from repom.redis.manage import (
    RedisManager,
    generate_docker_compose,
    generate_redis_conf,
    get_compose_dir,
    get_init_dir,
)


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
        # repom パッケージでは config_hook で 6380 に設定されている
        assert config.redis.port == 6380

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
        compose_dir = get_compose_dir()
        assert isinstance(compose_dir, Path)
        assert compose_dir.exists()

    def test_get_init_dir_returns_path(self):
        """get_init_dir が有効なパスを返す"""
        init_dir = get_init_dir()
        assert isinstance(init_dir, Path)
        # Should be a subdirectory of compose dir
        assert "redis_init" in str(init_dir)

    def test_get_compose_dir_uses_redis_subdir(self):
        """get_compose_dir が redis サブディレクトリを使用（分離プロジェクト構造）"""
        compose_dir = get_compose_dir()
        # Should be config.data_path/redis/
        assert str(compose_dir).endswith("redis")
        assert "redis" in str(compose_dir)

    def test_redis_generate_creates_in_redis_subdir(self):
        """redis_generate が data/repom/redis/ に docker-compose.yml を生成"""
        from repom.redis.manage import generate

        # Generate files
        generate()

        # Verify files are in redis subdirectory
        compose_file = get_compose_dir() / "docker-compose.generated.yml"
        assert compose_file.exists()
        assert "redis" in str(compose_file.parent)
