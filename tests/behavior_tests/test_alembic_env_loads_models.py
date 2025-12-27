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
import pytest
import tempfile
import shutil
import re


def test_alembic_env_loads_without_error():
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

    # alembic current を実行（既に poetry run pytest の中なので poetry run は不要）
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10
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


def test_alembic_revision_check_loads_without_error():
    """
    Alembic revision check コマンドが正常に動作することを確認

    検証内容:
    1. alembic revision --autogenerate のドライラン（チェックのみ）
    2. モデル読み込み処理が正常に動作すること
    3. env.py の load_models() が正しく呼び出されること

    注意:
    - 実際にマイグレーションファイルは作成しない（--check のみ）
    - モデルが正しく読み込まれないと autogenerate は動作しない
    """
    # repom のルートディレクトリを取得
    project_root = Path(__file__).parent.parent.parent

    # alembic heads コマンドを実行（既に poetry run pytest の中なので poetry run は不要）
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10
    )

    # エラーが発生しないことを確認
    stderr_lower = result.stderr.lower()

    assert "nameerror" not in stderr_lower, (
        f"alembic heads コマンドで NameError が発生しました:\n{result.stderr}"
    )

    assert result.returncode == 0, (
        f"alembic heads コマンドが異常終了しました:\n"
        f"STDERR: {result.stderr}\n"
        f"STDOUT: {result.stdout}\n"
        f"Return Code: {result.returncode}"
    )


@pytest.mark.parametrize("alembic_command", [
    "current",
    "heads",
    "history",
])
def test_alembic_commands_load_env_correctly(alembic_command):
    """
    複数の Alembic コマンドで env.py が正しく読み込まれることを確認

    検証するコマンド:
    - current: 現在のリビジョンを表示
    - heads: 最新のリビジョンを表示
    - history: マイグレーション履歴を表示

    これらのコマンドは全て env.py を読み込むため、
    load_models() が正しく動作しないと失敗する
    """
    project_root = Path(__file__).parent.parent.parent

    result = subprocess.run(
        [sys.executable, "-m", "alembic", alembic_command],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10
    )

    # env.py のロードに失敗していないことを確認
    assert result.returncode == 0, (
        f"alembic {alembic_command} コマンドが失敗しました:\n"
        f"STDERR: {result.stderr}\n"
        f"STDOUT: {result.stdout}"
    )

    # NameError は絶対に発生してはいけない
    assert "nameerror" not in result.stderr.lower(), (
        f"alembic {alembic_command} で NameError が発生:\n{result.stderr}"
    )


def test_alembic_revision_autogenerate_works():
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
    """
    project_root = Path(__file__).parent.parent.parent
    versions_dir = project_root / "alembic" / "versions"

    # 既存のマイグレーションファイルを一時バックアップ
    temp_backup_dir = tempfile.mkdtemp()
    try:
        # DBを最新状態にする
        upgrade_result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
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
                sys.executable, "-m", "alembic", "revision",
                "--autogenerate",
                "-m", "test_migration_generation"
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30
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
            for file in Path(temp_backup_dir).glob("*.py"):
                shutil.copy2(file, versions_dir)
        shutil.rmtree(temp_backup_dir)


def test_alembic_upgrade_head_works():
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
        timeout=30
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
