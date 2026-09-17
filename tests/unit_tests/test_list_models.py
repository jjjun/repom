"""Tests for the list_models script."""

from importlib.metadata import entry_points
from unittest.mock import patch

from basekit.discovery import DiscoveryFailure

from repom.scripts.list_models import list_models, main
from repom.utility import ModelInfo


class TestListModels:
    """Tests for the list_models() display function."""

    @patch('repom.scripts.list_models.describe_loaded_models')
    def test_list_models_returns_none(self, mock_describe):
        """list_models() must stay importable for direct callers that expect
        None, even though the console entry point now signals failures via
        its exit status (repom#165).
        """
        mock_describe.return_value = ([], [])

        assert list_models() is None

    @patch('repom.scripts.list_models.describe_loaded_models')
    def test_list_models_prints_model_list(self, mock_describe, capsys):
        mock_describe.return_value = (
            [
                ModelInfo(
                    name='User',
                    qualified_name='myapp.models.user.User',
                    table_name='users',
                    primary_key=['id'],
                    column_count=3,
                )
            ],
            [],
        )

        list_models()

        captured = capsys.readouterr()
        assert 'User' in captured.out
        assert 'users' in captured.out
        assert 'Total: 1 models' in captured.out

    @patch('repom.scripts.list_models.describe_loaded_models')
    def test_list_models_prints_import_failures(self, mock_describe, capsys):
        """A model module that failed to import must be named in the output,
        not silently dropped (repom#165).
        """
        mock_describe.return_value = (
            [],
            [
                DiscoveryFailure(
                    target='myapp.models.broken',
                    target_type='module',
                    exception_type='ImportError',
                    message='cannot import name broken_dependency',
                )
            ],
        )

        list_models()

        captured = capsys.readouterr()
        assert 'Model Import Failures' in captured.out
        assert 'myapp.models.broken' in captured.out
        assert 'ImportError' in captured.out
        assert 'cannot import name broken_dependency' in captured.out


class TestMain:
    """Tests for the console entry point."""

    @patch('repom.scripts.list_models.describe_loaded_models')
    def test_main_returns_zero_without_failures(self, mock_describe, capsys):
        mock_describe.return_value = ([], [])

        assert main() == 0

    @patch('repom.scripts.list_models.describe_loaded_models')
    def test_main_returns_one_with_failures(self, mock_describe, capsys):
        mock_describe.return_value = (
            [],
            [
                DiscoveryFailure(
                    target='myapp.models.broken',
                    target_type='module',
                    exception_type='ImportError',
                    message='cannot import name broken_dependency',
                )
            ],
        )

        result = main()

        captured = capsys.readouterr()
        assert result == 1
        assert 'Model Import Failures' in captured.out

    def test_main_reports_real_import_failure_and_exits_1(self, capsys):
        """With model_import_strict=False, a model module that fails to
        import must be named in the console output and the console entry
        must exit 1, instead of silently printing a partial list and
        exiting 0 (repom#165).
        """
        # Imported locally (not at module scope): some tests elsewhere in the
        # suite reload repom.config, which rebinds this name to a new
        # instance - a module-level import here would go stale for the rest
        # of the session and silently stop reflecting the live config.
        from repom.config import config

        original_locations = config.model_locations
        original_strict = config.model_import_strict
        original_prefixes = config.allowed_package_prefixes

        try:
            config.model_locations = ['tests.fixtures.broken_import']
            config.allowed_package_prefixes = {'tests.fixtures.'}
            config.model_import_strict = False

            result = main()

            captured = capsys.readouterr()
            assert result == 1
            assert 'Model Import Failures' in captured.out
            assert 'tests.fixtures.broken_import.broken_model' in captured.out
        finally:
            config.model_locations = original_locations
            config.model_import_strict = original_strict
            config.allowed_package_prefixes = original_prefixes

    def test_main_reports_disallowed_location_and_exits_1(self, capsys):
        """A model location outside allowed_package_prefixes raises a
        security ValueError from import_from_packages. It must be reported
        as a Model Import Failure with the console entry exiting 1, instead
        of letting the ValueError propagate (repom#165).
        """
        from repom.config import config

        original_locations = config.model_locations
        original_prefixes = config.allowed_package_prefixes
        original_strict = config.model_import_strict

        try:
            config.model_locations = ['os']
            config.allowed_package_prefixes = {'repom.'}
            config.model_import_strict = False

            result = main()

            captured = capsys.readouterr()
            assert result == 1
            assert 'Model Import Failures' in captured.out
            assert 'os' in captured.out
            assert 'ValueError' in captured.out
        finally:
            config.model_locations = original_locations
            config.model_import_strict = original_strict
            config.allowed_package_prefixes = original_prefixes

    def test_list_models_console_script_is_registered(self):
        """Test that the list_models console script is installed and exits
        via main(), not the plain list_models() function that returns None
        for direct callers (repom#165).
        """
        scripts = entry_points(group='console_scripts')
        list_models_script = [script for script in scripts if script.name == 'list_models']

        assert list_models_script
        assert list_models_script[0].value == 'repom.scripts.list_models:main'
