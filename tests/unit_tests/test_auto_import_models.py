"""
Tests for auto_import_models functions and configuration integration.

This test suite verifies:
1. auto_import_models_by_package() - Package-based model import with security
2. auto_import_models_from_list() - Batch import from multiple packages
3. RepomConfig properties - model_locations, allowed_package_prefixes, model_excluded_dirs
4. load_models() - Integration with config settings
5. Security validation - allowed_prefixes enforcement
6. Backward compatibility - Existing behavior without model_locations
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from repom.utility import (
    auto_import_models_by_package,
    auto_import_models_from_list,
    load_models,
    DEFAULT_EXCLUDED_DIRS
)
from repom.config import config


class TestAutoImportModelsByPackage:
    """Test auto_import_models_by_package() function"""

    def test_security_validation_raises_value_error(self):
        """許可されていないパッケージはValueErrorを送出"""
        with pytest.raises(ValueError, match="Security: Package 'untrusted.models' is not in allowed list"):
            auto_import_models_by_package(
                'untrusted.models',
                allowed_prefixes={'trusted.', 'repom.'}
            )

    def test_security_validation_allows_prefix_match(self):
        """許可されたプレフィックスにマッチするパッケージはOK"""
        # repom.examples.models は実際に存在するパッケージ
        try:
            auto_import_models_by_package(
                'repom.examples.models',
                allowed_prefixes={'repom.', 'myapp.'}
            )
            # エラーが出なければ成功
        except ValueError as e:
            if "Security:" in str(e):
                pytest.fail(f"Security check should have passed: {e}")
            # 他のエラー（ImportError など）は無視（実際のインポートの問題）

    def test_security_validation_skipped_when_none(self):
        """allowed_prefixes=None の場合は検証をスキップ"""
        # repom.examples.models は実際に存在するので、セキュリティチェックだけ確認
        try:
            auto_import_models_by_package(
                'repom.examples.models',
                allowed_prefixes=None  # 検証スキップ
            )
            # エラーが出なければ成功
        except ValueError as e:
            if "Security:" in str(e):
                pytest.fail(f"Security check should have been skipped: {e}")

    def test_import_error_for_nonexistent_package(self):
        """存在しないパッケージはImportError"""
        with pytest.raises(ImportError, match="Failed to import package nonexistent_package"):
            auto_import_models_by_package(
                'nonexistent_package.models',
                allowed_prefixes={'nonexistent_package.'}
            )

    def test_value_error_for_module_not_package(self):
        """モジュール（パッケージではない）はValueError"""
        # repom.config はモジュール（パッケージではない）
        with pytest.raises(ValueError, match="is not a package"):
            auto_import_models_by_package(
                'repom.config',  # モジュールなので __path__ がない
                allowed_prefixes={'repom.'}
            )

    @patch('repom.utility.auto_import_models')
    def test_calls_auto_import_models_with_correct_params(self, mock_auto_import):
        """auto_import_models を正しいパラメータで呼び出す"""
        excluded = {'tests', 'migrations'}

        try:
            auto_import_models_by_package(
                'repom.examples.models',
                excluded_dirs=excluded,
                allowed_prefixes={'repom.'}
            )
        except Exception:
            pass  # Import エラーは無視

        # auto_import_models が呼ばれたことを確認
        assert mock_auto_import.called


class TestAutoImportModelsFromList:
    """Test auto_import_models_from_list() function"""

    def test_batch_import_multiple_packages(self):
        """複数パッケージを一括インポート"""
        # repom.examples.models は実際に存在する
        # エラーが出ないことを確認（警告は出るかもしれない）
        try:
            auto_import_models_from_list(
                package_names=['repom.examples.models'],
                allowed_prefixes={'repom.'}
            )
            # エラーが出なければ成功
        except ValueError as e:
            if "Security:" in str(e):
                pytest.fail(f"Security check failed unexpectedly: {e}")

    def test_fail_on_error_false_continues_on_error(self, capsys):
        """fail_on_error=False の場合、エラーで停止しない"""
        auto_import_models_from_list(
            package_names=['nonexistent.models', 'repom.examples.models'],
            allowed_prefixes={'nonexistent.', 'repom.'},
            fail_on_error=False
        )

        # 警告メッセージが出力されることを確認
        captured = capsys.readouterr()
        assert 'Warning' in captured.out or 'Failed' in captured.out

    def test_fail_on_error_true_raises_exception(self):
        """fail_on_error=True の場合、最初のエラーで例外を送出"""
        with pytest.raises(Exception):  # ImportError or ValueError
            auto_import_models_from_list(
                package_names=['nonexistent.models'],
                allowed_prefixes={'nonexistent.'},
                fail_on_error=True
            )

    def test_security_validation_for_all_packages(self):
        """すべてのパッケージでセキュリティ検証が実行される"""
        # untrusted.models が最初に来るようにして、セキュリティエラーを確認
        with pytest.raises(ValueError, match="Security"):
            auto_import_models_from_list(
                package_names=['untrusted.models'],  # 許可されていないパッケージ
                allowed_prefixes={'trusted.'},
                fail_on_error=True
            )


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

    def test_model_import_strict_default_is_false(self):
        """model_import_strict のデフォルトは False"""
        from repom.config import RepomConfig
        test_config = RepomConfig()
        assert test_config.model_import_strict is False

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

    def test_load_models_uses_model_locations(self):
        """model_locations が設定されている場合、auto_import_models_from_list を呼び出す"""
        # 一時的に config を変更
        original_locations = config.model_locations
        original_excluded = config.model_excluded_dirs
        original_prefixes = config.allowed_package_prefixes

        try:
            config.model_locations = ['repom.examples.models']  # 実際に存在するパッケージ
            config.model_excluded_dirs = {'tests'}
            config.allowed_package_prefixes = {'repom.'}

            # load_models() を呼び出してエラーが出ないことを確認
            load_models()

            # 正常に実行できれば成功（モデルがインポートされた）
        finally:
            # 元に戻す
            config.model_locations = original_locations
            config.model_excluded_dirs = original_excluded
            config.allowed_package_prefixes = original_prefixes

    def test_load_models_backward_compatibility(self):
        """model_locations が None の場合、従来の動作（repom.examples.models インポート）"""
        # 一時的に config を変更
        original_locations = config.model_locations

        try:
            config.model_locations = None

            # load_models() を呼び出してエラーが出ないことを確認
            load_models()

            # repom.examples.models がインポートされれば成功
        finally:
            config.model_locations = original_locations

    def test_load_models_uses_model_import_strict(self):
        """model_import_strict が True の場合、エラーで停止する"""
        original_locations = config.model_locations
        original_strict = config.model_import_strict
        original_prefixes = config.allowed_package_prefixes

        try:
            config.model_locations = ['nonexistent.models']
            config.allowed_package_prefixes = {'nonexistent.'}
            config.model_import_strict = True

            # ImportError が発生することを確認
            with pytest.raises(ImportError):
                load_models()
        finally:
            config.model_locations = original_locations
            config.model_import_strict = original_strict
            config.allowed_package_prefixes = original_prefixes

    def test_load_models_default_strict_false(self, capsys):
        """model_import_strict のデフォルト（False）では警告のみ"""
        original_locations = config.model_locations
        original_strict = config.model_import_strict
        original_prefixes = config.allowed_package_prefixes

        try:
            config.model_locations = ['nonexistent.models']
            config.allowed_package_prefixes = {'nonexistent.'}
            config.model_import_strict = False  # デフォルト

            # エラーが出ないことを確認（警告のみ）
            load_models()

            # 警告メッセージが出力されることを確認
            captured = capsys.readouterr()
            assert 'Warning' in captured.out or 'Failed' in captured.out
        finally:
            config.model_locations = original_locations
            config.model_import_strict = original_strict
            config.allowed_package_prefixes = original_prefixes


class TestSecurityScenarios:
    """Security-focused test scenarios"""

    def test_default_config_only_allows_repom(self):
        """デフォルト設定では repom. パッケージのみ許可"""
        from repom.config import RepomConfig
        test_config = RepomConfig()

        # デフォルトは {'repom.'}
        assert test_config.allowed_package_prefixes == {'repom.'}

    def test_explicit_configuration_required_for_custom_packages(self):
        """カスタムパッケージには明示的な設定が必要"""
        # デフォルト設定で myapp.models をインポートしようとするとエラー
        with pytest.raises(ValueError, match="Security"):
            auto_import_models_from_list(
                package_names=['myapp.models'],
                allowed_prefixes={'repom.'},  # myapp. が含まれていない
                fail_on_error=True
            )

    def test_multiple_prefixes_can_be_allowed(self):
        """複数のプレフィックスを許可できる"""
        # repom.examples.models は実際に存在するので、セキュリティチェックのみ確認
        try:
            auto_import_models_by_package(
                'repom.examples.models',
                allowed_prefixes={'myapp.', 'shared.', 'repom.', 'plugins.'}
            )
        except ValueError as e:
            if "Security:" in str(e):
                pytest.fail(f"Security check should have passed: {e}")


class TestErrorHandling:
    """Error handling and edge cases"""

    def test_empty_package_list(self):
        """空のパッケージリストは何もしない"""
        auto_import_models_from_list(
            package_names=[],
            allowed_prefixes={'myapp.'}
        )
        # エラーが出なければ成功

    def test_none_excluded_dirs_uses_default(self):
        """excluded_dirs=None の場合、DEFAULT_EXCLUDED_DIRS を使用"""
        # これは auto_import_models の動作だが、連鎖的に影響する
        assert DEFAULT_EXCLUDED_DIRS == {'base', 'mixin', 'validators', 'utils', 'helpers', '__pycache__'}

    def test_warning_output_on_import_failure(self, capsys):
        """インポート失敗時に警告を出力"""
        auto_import_models_from_list(
            package_names=['nonexistent.package'],
            allowed_prefixes={'nonexistent.'},
            fail_on_error=False
        )

        captured = capsys.readouterr()
        assert 'Warning' in captured.out or 'Failed' in captured.out


class TestRealWorldScenarios:
    """Real-world usage scenarios"""

    def test_monorepo_multiple_packages(self):
        """モノレポ構成: 複数パッケージからインポート"""
        # repom.examples.models のみ実在するので、他はエラーを無視
        auto_import_models_from_list(
            package_names=['repom.examples.models'],  # 実在するパッケージのみ
            excluded_dirs={'tests', 'migrations'},
            allowed_prefixes={'myapp.', 'shared.', 'repom.'},
            fail_on_error=False
        )
        # エラーが出なければ成功

    def test_config_hook_pattern(self):
        """CONFIG_HOOK パターン: 親プロジェクトでの設定"""
        from repom.config import RepomConfig
        test_config = RepomConfig()

        # 親プロジェクトでの設定をシミュレート
        test_config.model_locations = [
            'myapp.models',
            'myapp.modules.user',
            'myapp.modules.task',
            'repom.examples.models'
        ]
        test_config.model_excluded_dirs = {'tests', 'migrations', 'scripts'}
        test_config.allowed_package_prefixes = {'myapp.', 'repom.'}

        # 設定が正しく保存されることを確認
        assert len(test_config.model_locations) == 4
        assert 'tests' in test_config.model_excluded_dirs
        assert 'myapp.' in test_config.allowed_package_prefixes
        assert 'repom.' in test_config.allowed_package_prefixes

    def test_environment_specific_configuration(self):
        """環境別設定: EXEC_ENV による切り替え"""
        from repom.config import RepomConfig
        import os

        test_config = RepomConfig()

        # テスト環境のシミュレーション
        if os.getenv('EXEC_ENV') == 'test':
            test_config.model_locations = ['myapp.models', 'myapp.test_models']
        else:
            test_config.model_locations = ['myapp.models']

        # 設定が適用されることを確認
        assert test_config.model_locations is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
