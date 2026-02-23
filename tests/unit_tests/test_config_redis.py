"""
Redis config support tests

このテストファイルは RepomConfig の Redis 関連プロパティのみをテストし、
実際のデータベース接続は行いません。
"""
import pytest
import os


class TestRedisProperties:
    """Redis connection properties tests"""

    def test_redis_host_default(self):
        """デフォルトは localhost"""
        from repom.config import RepomConfig
        config = RepomConfig()
        os.environ.pop('REDIS_HOST', None)
        assert config.redis.host == 'localhost'

    def test_redis_host_setter(self):
        """Setter で設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.redis.host = 'redis.example.com'
        assert config.redis.host == 'redis.example.com'

    def test_redis_port_default(self):
        """デフォルトは 6379"""
        from repom.config import RepomConfig
        config = RepomConfig()
        os.environ.pop('REDIS_PORT', None)
        assert config.redis.port == 6379

    def test_redis_port_setter(self):
        """Setter で設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.redis.port = 6380
        assert config.redis.port == 6380

    def test_redis_password_default(self):
        """デフォルトは None"""
        from repom.config import RepomConfig
        config = RepomConfig()
        os.environ.pop('REDIS_PASSWORD', None)
        assert config.redis.password is None

    def test_redis_password_setter(self):
        """Setter で設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.redis.password = 'mysecret'
        assert config.redis.password == 'mysecret'

    def test_redis_database_default(self):
        """デフォルトは 0"""
        from repom.config import RepomConfig
        config = RepomConfig()
        assert config.redis.database == 0

    def test_redis_database_setter(self):
        """Setter で設定"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.redis.database = 1
        assert config.redis.database == 1


class TestRedisContainerConfig:
    """Redis container configuration tests"""

    def test_get_container_name_default(self):
        """デフォルト: repom_redis"""
        from repom.config import RedisContainerConfig
        container = RedisContainerConfig()
        assert container.get_container_name() == 'repom_redis'

    def test_get_container_name_custom(self):
        """カスタム値で上書き可能"""
        from repom.config import RedisContainerConfig
        container = RedisContainerConfig(container_name='my_redis')
        assert container.get_container_name() == 'my_redis'

    def test_get_volume_name_default(self):
        """デフォルト: repom_redis_data"""
        from repom.config import RedisContainerConfig
        container = RedisContainerConfig()
        assert container.get_volume_name() == 'repom_redis_data'

    def test_get_volume_name_custom(self):
        """カスタム値で上書き可能"""
        from repom.config import RedisContainerConfig
        container = RedisContainerConfig(volume_name='my_redis_data')
        assert container.get_volume_name() == 'my_redis_data'

    def test_host_port_default(self):
        """ホストポート デフォルト: 6379"""
        from repom.config import RedisContainerConfig
        container = RedisContainerConfig()
        assert container.host_port == 6379

    def test_host_port_setter(self):
        """ホストポート Setter で設定"""
        from repom.config import RedisContainerConfig
        container = RedisContainerConfig(host_port=6380)
        assert container.host_port == 6380

    def test_image_default(self):
        """イメージ デフォルト: redis:7-alpine"""
        from repom.config import RedisContainerConfig
        container = RedisContainerConfig()
        assert container.image == 'redis:7-alpine'

    def test_image_setter(self):
        """イメージ Setter で設定"""
        from repom.config import RedisContainerConfig
        container = RedisContainerConfig(image='redis:latest')
        assert container.image == 'redis:latest'


class TestRedisConfigIntegration:
    """Redis config with RepomConfig integration tests"""

    def test_redis_config_in_repom_config(self):
        """RepomConfig が redis フィールドを持つ"""
        from repom.config import RepomConfig
        config = RepomConfig()
        assert hasattr(config, 'redis')
        assert config.redis.host == 'localhost'
        assert config.redis.port == 6379

    def test_redis_container_in_redis_config(self):
        """RedisConfig が container フィールドを持つ"""
        from repom.config import RepomConfig
        config = RepomConfig()
        assert hasattr(config.redis, 'container')
        assert config.redis.container.get_container_name() == 'repom_redis'
        assert config.redis.container.get_volume_name() == 'repom_redis_data'

    def test_redis_config_customization(self):
        """RedisConfig をカスタマイズ可能"""
        from repom.config import RepomConfig
        config = RepomConfig()
        config.redis.host = 'custom-host'
        config.redis.port = 7000
        config.redis.password = 'secret'
        config.redis.container.container_name = 'custom_redis'

        assert config.redis.host == 'custom-host'
        assert config.redis.port == 7000
        assert config.redis.password == 'secret'
        assert config.redis.container.get_container_name() == 'custom_redis'
