"""
Tests for generic discovery helpers in repom._.discovery
"""
import pytest
from repom._.discovery import (
    normalize_paths,
    DiscoveryFailure,
    DiscoveryError,
    validate_package_security,
    import_packages
)


class TestNormalizePaths:
    """normalize_paths() のテスト"""

    def test_single_string(self):
        assert normalize_paths("path1") == ["path1"]

    def test_comma_separated(self):
        assert normalize_paths("path1,path2,path3") == ["path1", "path2", "path3"]

    def test_list(self):
        assert normalize_paths(["path1", "path2"]) == ["path1", "path2"]

    def test_none(self):
        assert normalize_paths(None) == []

    def test_empty_string(self):
        assert normalize_paths("") == []

    def test_strip_whitespace(self):
        assert normalize_paths("  path1  , path2  ,  ") == ["path1", "path2"]

    def test_custom_separator(self):
        assert normalize_paths("path1;path2;path3", separator=';') == ["path1", "path2", "path3"]


class TestDiscoveryFailure:
    """DiscoveryFailure のテスト"""

    def test_to_dict(self):
        failure = DiscoveryFailure(
            target="myapp.routes",
            target_type="package",
            exception_type="ImportError",
            message="Not found"
        )
        assert failure.to_dict() == {
            "target": "myapp.routes",
            "target_type": "package",
            "exception_type": "ImportError",
            "message": "Not found"
        }

    def test_frozen(self):
        failure = DiscoveryFailure("test", "package", "Error", "message")
        with pytest.raises(AttributeError):
            failure.target = "modified"


class TestDiscoveryError:
    """DiscoveryError のテスト"""

    def test_single_failure(self):
        failures = [
            DiscoveryFailure("myapp.routes", "package", "ImportError", "Not found")
        ]
        error = DiscoveryError(failures)
        assert "Discovery failed with 1 error(s)" in str(error)
        assert "myapp.routes" in str(error)

    def test_multiple_failures(self):
        failures = [
            DiscoveryFailure("myapp.routes", "package", "ImportError", "Not found"),
            DiscoveryFailure("myapp.api", "package", "ModuleNotFoundError", "No module")
        ]
        error = DiscoveryError(failures)
        assert "Discovery failed with 2 error(s)" in str(error)
        assert "myapp.routes" in str(error)
        assert "myapp.api" in str(error)

    def test_failures_tuple(self):
        failures = [DiscoveryFailure("test", "package", "Error", "msg")]
        error = DiscoveryError(failures)
        assert isinstance(error.failures, tuple)
        assert len(error.failures) == 1


class TestValidatePackageSecurity:
    """validate_package_security() のテスト"""

    def test_allowed_package(self):
        # 例外が発生しないことを確認
        validate_package_security(
            "myapp.routes",
            allowed_prefixes={'myapp.', 'shared.'}
        )

    def test_allowed_exact_match(self):
        validate_package_security(
            "myapp.models.user",
            allowed_prefixes={'myapp.'}
        )

    def test_disallowed_package_strict(self):
        with pytest.raises(ValueError) as exc:
            validate_package_security(
                "malicious.code",
                allowed_prefixes={'myapp.', 'shared.'},
                strict=True
            )
        assert "Security" in str(exc.value)
        assert "malicious.code" in str(exc.value)

    def test_disallowed_package_non_strict(self, caplog):
        # 警告ログが出力されることを確認
        validate_package_security(
            "malicious.code",
            allowed_prefixes={'myapp.', 'shared.'},
            strict=False
        )
        assert "Security" in caplog.text
        assert "malicious.code" in caplog.text


class TestImportPackages:
    """import_packages() のテスト"""

    def test_import_valid_package(self):
        # os パッケージは常に利用可能
        failures = import_packages("os")
        assert failures == []

    def test_import_multiple_packages(self):
        failures = import_packages(["os", "sys", "pathlib"])
        assert failures == []

    def test_import_comma_separated(self):
        failures = import_packages("os,sys,pathlib")
        assert failures == []

    def test_import_nonexistent_package(self):
        failures = import_packages("nonexistent_package_12345")
        assert len(failures) == 1
        assert failures[0].target == "nonexistent_package_12345"
        assert failures[0].target_type == "package"
        assert failures[0].exception_type == "ModuleNotFoundError"

    def test_import_multiple_with_failures(self):
        failures = import_packages(["os", "nonexistent_1", "sys", "nonexistent_2"])
        assert len(failures) == 2
        assert failures[0].target == "nonexistent_1"
        assert failures[1].target == "nonexistent_2"

    def test_fail_on_error_false(self):
        # 失敗してもリストで返す
        failures = import_packages("nonexistent", fail_on_error=False)
        assert len(failures) == 1

    def test_fail_on_error_true(self):
        # 失敗時に例外を発生
        with pytest.raises(DiscoveryError) as exc:
            import_packages("nonexistent", fail_on_error=True)
        assert len(exc.value.failures) == 1

    def test_with_security_validation(self):
        # セキュリティ検証が動作することを確認
        with pytest.raises(DiscoveryError):
            import_packages(
                "os",
                allowed_prefixes={'myapp.'},
                fail_on_error=True
            )

    def test_returns_empty_list_on_success(self):
        failures = import_packages(["os", "sys"])
        assert isinstance(failures, list)
        assert len(failures) == 0
