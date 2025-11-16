"""Tests for Alembic configuration via MineDbConfig."""
import pytest
from pathlib import Path
from repom.config import MineDbConfig


def test_alembic_versions_path_default():
    """デフォルトの alembic_versions_path が正しいことを確認"""
    config = MineDbConfig()
    # root_path を明示的に設定（通常は config.py で設定される）
    config.root_path = str(Path(__file__).parent.parent.parent)
    config.init()

    expected_path = str(Path(config.root_path) / 'alembic' / 'versions')
    assert config.alembic_versions_path == expected_path
    assert 'alembic/versions' in config.alembic_versions_path or 'alembic\\versions' in config.alembic_versions_path


def test_alembic_versions_path_custom():
    """カスタム alembic_versions_path が正しく設定されることを確認"""
    config = MineDbConfig()
    custom_path = '/custom/path/to/versions'
    config._alembic_versions_path = custom_path

    assert config.alembic_versions_path == custom_path


def test_alembic_versions_path_inheritance():
    """継承したクラスで alembic_versions_path を上書きできることを確認"""
    class CustomConfig(MineDbConfig):
        def __init__(self):
            super().__init__()
            self._alembic_versions_path = '/external/project/alembic/versions'

    config = CustomConfig()
    assert config.alembic_versions_path == '/external/project/alembic/versions'


def test_external_project_simulation():
    """外部プロジェクト（mine-py など）の設定をシミュレート"""
    class ExternalProjectConfig(MineDbConfig):
        def __init__(self, project_root: Path):
            super().__init__()
            self.root_path = str(project_root)
            # 外部プロジェクトのカスタムパス
            self._alembic_versions_path = str(project_root / 'migrations' / 'versions')

    project_root = Path('/home/user/external_project')
    config = ExternalProjectConfig(project_root)

    expected_path = str(project_root / 'migrations' / 'versions')
    assert config.alembic_versions_path == expected_path


def test_repom_and_external_project_isolation():
    """repom と外部プロジェクトのパスが独立していることを確認"""
    # repom の設定
    repom_config = MineDbConfig()
    repom_config.root_path = str(Path(__file__).parent.parent.parent)
    repom_config.init()

    # 外部プロジェクトの設定
    class ExternalConfig(MineDbConfig):
        def __init__(self):
            super().__init__()
            self.root_path = '/external'  # root_path も設定
            self._alembic_versions_path = '/external/migrations/versions'

    external_config = ExternalConfig()

    # パスが異なることを確認
    assert repom_config.alembic_versions_path != external_config.alembic_versions_path
    assert 'external' in external_config.alembic_versions_path
    assert 'external' not in repom_config.alembic_versions_path


def test_alembic_versions_path_can_be_outside_alembic_dir():
    """alembic_versions_path が alembic ディレクトリの外側に配置可能なことを確認"""
    config = MineDbConfig()
    config.root_path = '/project'

    # migrations/versions のような別の場所を指定
    config._alembic_versions_path = '/project/database/migrations/versions'

    assert config.alembic_versions_path == '/project/database/migrations/versions'
    # alembic ディレクトリとは無関係
    assert 'alembic' not in config.alembic_versions_path
