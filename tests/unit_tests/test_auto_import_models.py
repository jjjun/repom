"""Tests for repom model import configuration and load_models integration."""

import logging

import pytest
from unittest.mock import ANY, patch

from repom.config import config
from repom.logging import get_logger
from repom.utility import DEFAULT_EXCLUDED_DIRS, DiscoveryError, load_models


class TestRepomConfigProperties:
    """Test RepomConfig properties for model import configuration"""

    def test_model_locations_default_is_empty_list(self):
        """model_locations のデフォルトは空リスト"""
        from repom.config import RepomConfig
        test_config = RepomConfig()
        assert test_config.model_locations == []

    def test_model_locations_setter_and_getter(self):
        """model_locations の setter/getter が正常に動作"""
        from repom.config import RepomConfig
        test_config = RepomConfig()

        test_config.model_locations = ['myapp.models', 'shared.models']
        assert test_config.model_locations == ['myapp.models', 'shared.models']

    def test_model_excluded_dirs_default_is_empty_set(self):
        """model_excluded_dirs のデフォルトは空セット"""
        from repom.config import RepomConfig
        test_config = RepomConfig()
        assert test_config.model_excluded_dirs == set()

    def test_model_excluded_dirs_setter_and_getter(self):
        """model_excluded_dirs の setter/getter が正常に動作"""
        from repom.config import RepomConfig
        test_config = RepomConfig()

        excluded = {'tests', 'migrations', 'scripts'}
        test_config.model_excluded_dirs = excluded
        assert test_config.model_excluded_dirs == excluded

    def test_allowed_package_prefixes_default(self):
        """allowed_package_prefixes のデフォルトは {'repom.'}"""
        from repom.config import RepomConfig
        test_config = RepomConfig()
        assert test_config.allowed_package_prefixes == {'repom.'}

    def test_allowed_package_prefixes_setter_and_getter(self):
        """allowed_package_prefixes の setter/getter が正常に動作"""
        from repom.config import RepomConfig
        test_config = RepomConfig()

        prefixes = {'myapp.', 'shared.', 'repom.'}
        test_config.allowed_package_prefixes = prefixes
        assert test_config.allowed_package_prefixes == prefixes

    def test_model_import_strict_defaults_to_true(self):
        """model_import_strict のデフォルトは True

        alembic autogenerate や db_create が partial な Base.metadata に対して
        破壊的な操作を行わないよう、import failure はデフォルトで例外にする。
        """
        from repom.config import RepomConfig
        test_config = RepomConfig()
        assert test_config.model_import_strict is True

    def test_model_import_strict_setter_and_getter(self):
        """model_import_strict の setter/getter が正常に動作"""
        from repom.config import RepomConfig
        test_config = RepomConfig()

        test_config.model_import_strict = True
        assert test_config.model_import_strict is True

        test_config.model_import_strict = False
        assert test_config.model_import_strict is False


class TestLoadModelsIntegration:
    """Test load_models() function integration with config"""

    def test_load_models_logs_one_summary_without_model_names(self, caplog):
        with caplog.at_level('DEBUG', logger='repom.utility'):
            load_models()

        summary_records = [
            record
            for record in caplog.records
            if record.name == 'repom.utility'
            and record.levelname == 'DEBUG'
            and record.getMessage().startswith('Loaded ')
        ]

        assert len(summary_records) == 1
        assert 'models in ' in summary_records[0].getMessage()

    def test_load_models_logs_model_names_when_detail_logger_is_enabled(self, caplog):
        detail_logger = get_logger('repom.utility').getChild('models.detail')
        original_level = detail_logger.level

        detail_logger.setLevel(logging.DEBUG)
        caplog.set_level(logging.DEBUG)
        try:
            load_models()
        finally:
            detail_logger.setLevel(original_level)

        detail_records = [
            record
            for record in caplog.records
            if record.name == detail_logger.name
        ]

        assert len(detail_records) == 1
        assert detail_records[0].getMessage().startswith('Loaded models:')

    def test_load_models_uses_model_locations(self, monkeypatch):
        """model_locations が設定されている場合、auto_import_models_from_list を呼び出す"""
        with patch('repom.utility.import_from_packages', return_value=[]) as import_models:
            monkeypatch.setattr(config, 'model_locations', ['repom.examples.models'])
            monkeypatch.setattr(config, 'model_excluded_dirs', {'tests'})
            monkeypatch.setattr(config, 'allowed_package_prefixes', {'repom.'})

            failures = load_models()

        assert failures == []
        import_models.assert_called_once_with(
            package_names=['repom.examples.models'],
            excluded_dirs={'tests'},
            allowed_prefixes={'repom.'},
            fail_on_error=False,
            post_import_hook=ANY,
        )

    def test_load_models_skips_import_when_model_locations_are_unset(self, monkeypatch):
        """Unset model locations must not trigger the removed default import."""
        with patch('repom.utility.import_from_packages') as import_models:
            monkeypatch.setattr(config, 'model_locations', None)

            failures = load_models()

        assert failures == []
        import_models.assert_not_called()

    def test_load_models_uses_model_import_strict(self):
        """model_import_strict が True の場合、エラーで停止する"""
        original_locations = config.model_locations
        original_strict = config.model_import_strict
        original_prefixes = config.allowed_package_prefixes

        try:
            config.model_locations = ['nonexistent.models']
            config.allowed_package_prefixes = {'nonexistent.'}
            config.model_import_strict = True

            # DiscoveryError が発生することを確認
            with pytest.raises(DiscoveryError):
                load_models()
        finally:
            config.model_locations = original_locations
            config.model_import_strict = original_strict
            config.allowed_package_prefixes = original_prefixes

    def test_load_models_strict_false_does_not_raise(self):
        """model_import_strict を明示的に False にした場合は例外を発生させない"""
        original_locations = config.model_locations
        original_strict = config.model_import_strict
        original_prefixes = config.allowed_package_prefixes

        try:
            config.model_locations = ['nonexistent.models']
            config.allowed_package_prefixes = {'nonexistent.'}
            config.model_import_strict = False  # 明示的なオプトアウト

            failures = load_models()

            assert len(failures) == 1
            assert failures[0].target == 'nonexistent.models'
        finally:
            config.model_locations = original_locations
            config.model_import_strict = original_strict
            config.allowed_package_prefixes = original_prefixes

    def test_load_models_logs_and_returns_failures(self, caplog):
        """import に失敗したモジュールは ERROR ログに記録され、失敗リストに
        名前が含まれて返される（黙って捨てられない）。
        """
        original_locations = config.model_locations
        original_strict = config.model_import_strict
        original_prefixes = config.allowed_package_prefixes

        try:
            config.model_locations = ['tests.fixtures.broken_import']
            config.allowed_package_prefixes = {'tests.fixtures.'}
            config.model_import_strict = False

            with caplog.at_level('ERROR', logger='repom.utility'):
                failures = load_models()

            assert len(failures) == 1
            assert failures[0].target == 'tests.fixtures.broken_import.broken_model'
            assert failures[0].exception_type == 'RuntimeError'

            error_records = [
                record for record in caplog.records
                if record.name == 'repom.utility' and record.levelname == 'ERROR'
            ]
            assert len(error_records) == 1
            assert 'tests.fixtures.broken_import.broken_model' in error_records[0].getMessage()
        finally:
            config.model_locations = original_locations
            config.model_import_strict = original_strict
            config.allowed_package_prefixes = original_prefixes


class TestRepomDiscoveryDefaults:
    """Repom-specific model discovery defaults."""

    def test_utility_default_excluded_directories_include_model_dirs(self):
        # これは auto_import_models の動作だが、連鎖的に影響する
        # discovery.py の DEFAULT_EXCLUDED_DIRS は汎用的
        assert DEFAULT_EXCLUDED_DIRS == {'base', 'mixin', 'validators', 'utils', 'helpers', '__pycache__'}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
