"""Integration test for Alembic env.py model loading

このテストは Alembic の env.py が正しくモデルを読み込めることを確認します。
alembic current コマンドを実行して、env.py のロード処理が成功することを検証します。

目的:
- alembic/env.py の load_models() 呼び出しが正しく動作すること
- Alembic コマンド実行時にモデルが正しく読み込まれること
- NameError などの実行時エラーが発生しないこと
"""

import subprocess
import sys
from pathlib import Path
import os
import shutil
import re


def alembic_test_env(test_root: Path):
    env = os.environ.copy()
    env["EXEC_ENV"] = "test"
    env["DB_TYPE"] = "sqlite"
    env["CONFIG_HOOK"] = "alembic_test_config:hook_config"
    env["REPOM_TEST_ROOT"] = str(test_root)
    project_root = Path(__file__).parent.parent.parent.resolve()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(project_root / "tests"), env.get("PYTHONPATH", "")]
    )
    return env


def test_alembic_env_loads_without_error(tmp_path):
    """
    Alembic の env.py が正しく読み込まれ、モデルロード処理が成功することを確認

    検証内容:
    1. alembic current コマンドが正常に実行できること
    2. NameError などの実行時エラーが発生しないこと
    3. 標準エラー出力にエラーメッセージが含まれないこと

    なぜこのテストが必要か:
    - env.py 内で存在しない関数を呼び出すと NameError になる
    - load_models() の呼び出しが正しくないと Alembic が動作しない
    - マイグレーション実行前にこの問題を検知できる
    """
    # repom のルートディレクトリを取得
    project_root = Path(__file__).parent.parent.parent

    # alembic current を実行（既に uv run pytest の中なので uv run は不要）
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10,
        env=alembic_test_env(tmp_path),
    )

    # 実行結果を確認
    stderr_lower = result.stderr.lower()

    # NameError は絶対に発生してはいけない
    assert "nameerror" not in stderr_lower, (
        f"alembic current コマンドで NameError が発生しました:\n"
        f"STDERR: {result.stderr}\n"
        f"STDOUT: {result.stdout}\n"
        f"Return Code: {result.returncode}\n\n"
        f"原因: alembic/env.py で存在しない関数が呼び出されている可能性があります。"
    )

    # ImportError も発生してはいけない
    assert "importerror" not in stderr_lower, (
        f"alembic current コマンドで ImportError が発生しました:\n"
        f"STDERR: {result.stderr}\n"
        f"STDOUT: {result.stdout}\n"
        f"Return Code: {result.returncode}\n\n"
        f"原因: alembic/env.py のインポート文が間違っている可能性があります。"
    )

    # AttributeError も発生してはいけない
    assert "attributeerror" not in stderr_lower, (
        f"alembic current コマンドで AttributeError が発生しました:\n"
        f"STDERR: {result.stderr}\n"
        f"STDOUT: {result.stdout}\n"
        f"Return Code: {result.returncode}\n\n"
        f"原因: 存在しない属性やメソッドが呼び出されている可能性があります。"
    )

    # コマンドが正常終了すること（リターンコード 0）
    assert result.returncode == 0, (
        f"alembic current コマンドが異常終了しました:\n"
        f"STDERR: {result.stderr}\n"
        f"STDOUT: {result.stdout}\n"
        f"Return Code: {result.returncode}\n\n"
        f"env.py の実行に失敗している可能性があります。"
    )


def test_alembic_revision_autogenerate_works(tmp_path):
    """
    Alembic の autogenerate 機能が正しく動作することを確認

    検証内容:
    1. alembic revision --autogenerate が正常に動作すること
    2. マイグレーションファイルが正しく生成されること
    3. 生成されたファイルに基本的な構造が含まれていること

    なぜこのテストが必要か:
    - autogenerate はモデルを読み込んでスキーマを比較する
    - load_models() が正しく動作しないと autogenerate も失敗する
    - 生成されるマイグレーションファイルの品質を保証できる

    Note:
        SQLITE_USE_FILE_DB=1 を使用（test 環境のデフォルトは in-memory SQLite のため、
        subprocess 間でDB状態が保持されない）
    """
    project_root = Path(__file__).parent.parent.parent.resolve()
    versions_dir = tmp_path / "alembic" / "versions"
    versions_dir.mkdir(parents=True)
    ini_path = tmp_path / "alembic.ini"
    ini_content = (project_root / "alembic.ini").read_text(encoding="utf-8")
    ini_content = ini_content.replace(
        "script_location = alembic",
        f"script_location = {project_root / 'alembic'}",
        1,
    )
    ini_content = ini_content.replace(
        "version_locations = alembic/versions",
        "version_locations = %(here)s/alembic/versions",
        1,
    )
    ini_path.write_text(ini_content, encoding="utf-8")

    # test 環境でファイルベースDB を使用（in-memory は subprocess 間で状態が保持されない）
    test_env = alembic_test_env(tmp_path)
    test_env["SQLITE_USE_FILE_DB"] = "1"
    alembic_command = [sys.executable, "-m", "alembic", "-c", str(ini_path)]

    # 既存のマイグレーションファイルを一時バックアップ
    temp_backup_dir = tmp_path / "versions_backup"
    temp_backup_dir.mkdir()
    try:
        # DBを最新状態にする
        upgrade_result = subprocess.run(
            [*alembic_command, "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
            env=test_env
        )

        assert upgrade_result.returncode == 0, (
            f"alembic upgrade head が失敗しました（前提条件）:\n"
            f"STDERR: {upgrade_result.stderr}\n"
            f"STDOUT: {upgrade_result.stdout}"
        )

        # versions ディレクトリの全ファイルをバックアップ
        if versions_dir.exists():
            for file in versions_dir.glob("*.py"):
                if file.name != "__pycache__":
                    shutil.copy2(file, temp_backup_dir)

        # テスト用のマイグレーションファイルを生成
        result = subprocess.run(
            [
                *alembic_command,
                "revision",
                "--autogenerate",
                "-m",
                "test_migration_generation",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
            env=test_env
        )

        # コマンドが成功すること
        assert result.returncode == 0, (
            f"alembic revision --autogenerate が失敗しました:\n"
            f"STDERR: {result.stderr}\n"
            f"STDOUT: {result.stdout}"
        )

        # NameError が発生していないこと
        assert "nameerror" not in result.stderr.lower(), (
            f"autogenerate で NameError が発生:\n{result.stderr}"
        )

        # マイグレーションファイルが生成されたことを確認
        # 出力から生成されたファイル名を抽出
        # 例: "Generating C:\...\alembic\versions\abc123_test_migration_generation.py"
        generated_file_match = re.search(
            r"Generating\s+.*versions[/\\]([a-f0-9]+_.*\.py)",
            result.stdout,
            re.IGNORECASE | re.DOTALL
        )

        assert generated_file_match, (
            f"マイグレーションファイルのパスが見つかりません:\n{result.stdout}"
        )

        generated_filename = generated_file_match.group(1)
        generated_file = versions_dir / generated_filename

        assert generated_file.exists(), (
            f"マイグレーションファイルが生成されていません: {generated_file}"
        )

        # 生成されたファイルの内容を確認
        content = generated_file.read_text(encoding='utf-8')

        # 基本的な構造が含まれていること
        assert "def upgrade()" in content, (
            "マイグレーションファイルに upgrade() 関数がありません"
        )
        assert "def downgrade()" in content, (
            "マイグレーションファイルに downgrade() 関数がありません"
        )
        # Python 3.12+ では型ヒント付き: revision: str = 'xxx'
        assert "revision:" in content or "revision =" in content, (
            "マイグレーションファイルに revision 情報がありません"
        )

        # テスト用のマイグレーションファイルを削除
        generated_file.unlink()

    finally:
        # バックアップを復元
        if versions_dir.exists():
            for file in temp_backup_dir.glob("*.py"):
                shutil.copy2(file, versions_dir)


def test_alembic_upgrade_head_works(tmp_path):
    """
    Alembic upgrade head が正常に動作することを確認

    検証内容:
    1. alembic upgrade head が正常に実行できること
    2. マイグレーションの適用処理が成功すること
    3. エラーが発生しないこと

    なぜこのテストが必要か:
    - upgrade はマイグレーションを実際にDBに適用する
    - load_models() が正しく動作しないと upgrade も失敗する
    - 本番環境でのマイグレーション実行前に問題を検知できる
    """
    project_root = Path(__file__).parent.parent.parent

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=30,
        env=alembic_test_env(tmp_path),
    )

    # コマンドが成功すること
    assert result.returncode == 0, (
        f"alembic upgrade head が失敗しました:\n"
        f"STDERR: {result.stderr}\n"
        f"STDOUT: {result.stdout}"
    )

    # NameError が発生していないこと
    assert "nameerror" not in result.stderr.lower(), (
        f"upgrade head で NameError が発生:\n{result.stderr}"
    )
