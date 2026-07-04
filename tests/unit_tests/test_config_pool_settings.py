"""RepomConfig の接続プール設定プロパティと engine_kwargs 連携のテスト。"""

import pytest

from repom.config import RepomConfig


class TestPoolSettingDefaults:
    """デフォルト値の確認"""

    def test_defaults(self):
        config = RepomConfig()
        assert config.db_pool_size == 10
        assert config.db_max_overflow == 20
        assert config.db_pool_timeout == 30
        assert config.db_pool_recycle == 3600
        assert config.db_pool_pre_ping is True


class TestPoolSettingValidation:
    """setter のバリデーション"""

    def test_pool_size_must_be_positive(self):
        config = RepomConfig()
        with pytest.raises(ValueError, match="db_pool_size"):
            config.db_pool_size = 0

    def test_max_overflow_must_be_non_negative(self):
        config = RepomConfig()
        with pytest.raises(ValueError, match="db_max_overflow"):
            config.db_max_overflow = -1

    def test_pool_timeout_must_be_non_negative(self):
        config = RepomConfig()
        with pytest.raises(ValueError, match="db_pool_timeout"):
            config.db_pool_timeout = -1

    def test_pool_recycle_allows_minus_one(self):
        config = RepomConfig()
        config.db_pool_recycle = -1
        assert config.db_pool_recycle == -1

    def test_pool_recycle_rejects_below_minus_one(self):
        config = RepomConfig()
        with pytest.raises(ValueError, match="db_pool_recycle"):
            config.db_pool_recycle = -2


class TestEngineKwargsReflectPoolSettings:
    """engine_kwargs が設定値を反映することを確認"""

    def test_postgres_reflects_configured_values(self):
        config = RepomConfig()
        config.db_type = "postgres"
        config.db_pool_size = 5
        config.db_max_overflow = 7
        config.db_pool_timeout = 15
        config.db_pool_recycle = 1800
        config.db_pool_pre_ping = False

        kwargs = config.engine_kwargs

        assert kwargs["pool_size"] == 5
        assert kwargs["max_overflow"] == 7
        assert kwargs["pool_timeout"] == 15
        assert kwargs["pool_recycle"] == 1800
        assert kwargs["pool_pre_ping"] is False

    def test_sqlite_file_reflects_configured_values(self):
        config = RepomConfig()
        config.db_type = "sqlite"
        config.root_path = "/tmp/repom"
        config.sqlite.use_in_memory_for_tests = False
        config.init()
        config.db_pool_size = 3
        config.db_max_overflow = 4
        config.db_pool_timeout = 12
        config.db_pool_recycle = 900
        config.db_pool_pre_ping = False

        kwargs = config.engine_kwargs

        assert kwargs["pool_size"] == 3
        assert kwargs["max_overflow"] == 4
        assert kwargs["pool_timeout"] == 12
        assert kwargs["pool_recycle"] == 900
        assert kwargs["pool_pre_ping"] is False

    def test_sqlite_memory_ignores_pool_settings(self):
        config = RepomConfig()
        config.db_type = "sqlite"
        config.root_path = "/tmp/repom"
        config._db_url = "sqlite:///:memory:"
        config.db_pool_size = 3

        kwargs = config.engine_kwargs

        # StaticPool ブランチは pool_size を持たない（変更なし）
        assert "pool_size" not in kwargs
        assert kwargs["poolclass"].__name__ == "StaticPool"
