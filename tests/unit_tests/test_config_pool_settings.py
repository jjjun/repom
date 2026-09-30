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
