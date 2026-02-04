# Issue #031: Alembic セットアップとリセットユーティリティの実装

**ステータス**: 🟡 提案中

**作成日**: 2026-02-04

**優先度**: 中

**複雑度**: 中

---

## 問題の説明

現在、repom を使う外部プロジェクト（mine-py など）で Alembic のセットアップやマイグレーションのリセット（初期化）を行うための統一的なユーティリティが存在しません。

**repom の方針**:
- repom 内部で alembic の処理を統合
- **env.py, script.py.mako は repom が提供**（`repom/alembic/` 配下に既存）
- 外部プロジェクトは alembic.ini とマイグレーションファイル保存ディレクトリのみ用意すれば使える

**現状の課題**:

1. **外部プロジェクトでの初回セットアップが手作業**
   - alembic.ini の作成が手動（設定ミスが起きやすい）
   - version_locations ディレクトリの作成が手動
   - 既存ファイルの有無を確認せずに上書きするリスク

2. **テストでのマイグレーション管理が煩雑**
   - `test_migration_no_id.py` などで、テストごとに alembic.ini を手動で生成している
   - 約60行の重複コードが複数のテストファイルに散在
   - テスト用の一時ディレクトリ、DB URL、version_locations の設定が毎回必要

3. **開発時のマイグレーションリセットが手作業**
   - マイグレーションファイルを手動で削除
   - alembic_version テーブルを手動で削除
   - 初期セットアップを手動でやり直す

**具体的な重複コード例**:

```python
# test_migration_no_id.py の中で毎回実行
def _get_alembic_ini_content(alembic_dir, db_url):
    """Generate alembic.ini content for testing"""
    return f"""
[alembic]
script_location = {alembic_dir}
file_template = %%(rev)s_%%(slug)s
sqlalchemy.url = {db_url}
# ... 60行のテンプレート
"""

# 同様のコードが test_alembic_env_loads_models.py にも存在
```

**注意**: env.py と script.py.mako は repom が既に提供しているため、外部プロジェクトやテストで生成する必要はありません。

---

## 期待される動作

Alembic のセットアップとリセットを行う統一的なユーティリティを提供し、テストとスクリプトの両方で使用可能にする。

**提供する機能**:

1. **alembic.ini ファイル生成**
   - パラメータベースで alembic.ini を生成
   - 既存ファイルがある場合は上書きしない（安全）
   - テンプレート方式で柔軟な設定を可能に

2. **version_locations ディレクトリの作成**
   - 必要なディレクトリ構造を自動作成
   - 既存ディレクトリがある場合は何もしない

3. **マイグレーションファイルの一括削除**
   - version_locations 内の全 .py ファイルを削除
   - `__init__.py` や `__pycache__` は保護

4. **マイグレーション管理テーブルの削除**
   - `alembic_version` テーブルを安全に削除

**注意**: env.py と script.py.mako は repom が提供するため、このユーティリティでは生成しません。

**使用例（テスト）**:

```python
# tests/behavior_tests/test_migration_no_id.py
from repom.alembic.setup import AlembicSetup

def test_alembic_migration_without_id():
    with tempfile.TemporaryDirectory() as tmpdir:
        setup = AlembicSetup(
            project_root=tmpdir,
            db_url=f'sqlite:///{tmpdir}/test.db'
        )
        
        # alembic.ini を自動生成（env.py は repom が提供）
        setup.create_alembic_ini()
        
        # マイグレーション実行
        alembic_cfg = setup.get_alembic_config()
        command.revision(alembic_cfg, message="test", autogenerate=True)
        
        # クリーンアップ
        setup.reset_migrations()
```

**使用例（スクリプト）**:

```bash
# マイグレーションを完全リセット
poetry run alembic_reset

# 外部プロジェクトの初回セットアップ
poetry run alembic_init --project-root . --version-locations ./alembic/versions
```

---

## 提案される解決策

### アーキテクチャ

```
repom/
├── alembic/
│   ├── __init__.py
│   ├── env.py             # repom が提供（既存）
│   ├── script.py.mako     # repom が提供（既存）
│   ├── setup.py           # AlembicSetup クラス（新規）
│   ├── templates.py       # alembic.ini テンプレート（新規）
│   └── reset.py           # リセット機能（新規）
└── scripts/
    ├── alembic_init.py    # 初回セットアップスクリプト（新規）
    └── alembic_reset.py   # リセットスクリプト（新規）
```

### 1. AlembicSetup クラス（コア）

**責務**: Alembic のセットアップと管理を統括

```python
# repom/alembic/setup.py
from pathlib import Path
from typing import Optional
from alembic.config import Config as AlembicConfig
from repom.alembic.templates import AlembicTemplates
from repom.alembic.reset import AlembicReset

class AlembicSetup:
    """Alembic セットアップと管理のための統合ユーティリティ
    
    テストとスクリプトの両方で使用可能。
    """
    
    def __init__(
        self,
        project_root: str | Path,
        db_url: Optional[str] = None,
        script_location: Optional[str] = None,
        version_locations: Optional[str] = None
    ):
        """
        Args:
            project_root: プロジェクトルートディレクトリ
            db_url: データベース URL（省略時は RepomConfig から取得）
            script_location: alembic スクリプトの場所（省略時: 'alembic'）
            version_locations: マイグレーションファイルの保存場所
        """
        self.project_root = Path(project_root)
        self.db_url = db_url or self._get_default_db_url()
        self.script_location = script_location or "alembic"
        self.version_locations = version_locations or "alembic/versions"
        
        self.alembic_dir = self.project_root / self.script_location
        self.versions_dir = self.project_root / self.version_locations
        
    def create_alembic_ini(self, overwrite: bool = False) -> None:
        """alembic.ini を生成
        
        Args:
            overwrite: 既存ファイルを上書きするか（デフォルト: False）
        
        Note:
            env.py と script.py.mako は repom が提供するため、生成しません。
        """
        ini_path = self.project_root / "alembic.ini"
        
        # 既存ファイルがある場合は上書きしない（安全）
        if ini_path.exists() and not overwrite:
            print(f"✓ alembic.ini already exists: {ini_path}")
            return
        
        content = AlembicTemplates.generate_alembic_ini(
            script_location=self.script_location,
            version_locations=self.version_locations,
            db_url=self.db_url
        )
        ini_path.write_text(content, encoding='utf-8')
        print(f"✓ Created alembic.ini: {ini_path}")
    
    def create_version_directory(self) -> None:
        """version_locations ディレクトリを作成"""
        if self.versions_dir.exists():
            print(f"✓ Version directory already exists: {self.versions_dir}")
            return
        
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        
        # __init__.py を作成（Python パッケージとして認識させる）
        init_file = self.versions_dir / "__init__.py"
        init_file.touch()
        print(f"✓ Created version directory: {self.versions_dir}")
    
    def reset_migrations(
        self,
        drop_table: bool = True,
        delete_files: bool = True
    ) -> None:
        """マイグレーションをリセット
        
        Args:
            drop_table: alembic_version テーブルを削除するか
            delete_files: マイグレーションファイルを削除するか
        """
        reset = AlembicReset(
            db_url=self.db_url,
            versions_dir=self.versions_dir
        )
        
        if drop_table:
            reset.drop_alembic_version_table()
        
        if delete_files:
            reset.delete_migration_files()
    
    def get_alembic_config(self) -> AlembicConfig:
        """Alembic Config オブジェクトを取得"""
        ini_path = self.project_root / "alembic.ini"
        if not ini_path.exists():
            raise FileNotFoundError(
                f"alembic.ini not found at {ini_path}. "
                f"Run create_config_files() first."
            )
        
        config = AlembicConfig(str(ini_path))
        config.set_main_option("sqlalchemy.url", self.db_url)
        return config
    
    def _get_default_db_url(self) -> str:
        """デフォルトの DB URL を取得"""
        from repom.config import config
        return config.db_url
```

### 2. テンプレート管理

**責務**: alembic.ini のテンプレート提供

**注意**: env.py と script.py.mako は repom が既に提供しているため、このモジュールでは alembic.ini のみ生成します。

```python
# repom/alembic/templates.py
class AlembicTemplates:
    """Alembic 設定ファイルのテンプレート提供"""
    
    @staticmethod
    def generate_alembic_ini(
        script_location: str,
        version_locations: str,
        db_url: str
    ) -> str:
        """alembic.ini を生成"""
        return f"""# A generic, single database configuration.

[alembic]
script_location = {script_location}
version_locations = {version_locations}
file_template = %%(rev)s_%%(slug)s
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""
```

### 3. リセット機能

**責務**: マイグレーション関連のデータとファイルを削除

```python
# repom/alembic/reset.py
from pathlib import Path
from sqlalchemy import create_engine, text
from typing import Optional

class AlembicReset:
    """Alembic マイグレーションのリセット機能"""
    
    def __init__(
        self,
        db_url: str,
        versions_dir: Path
    ):
        self.db_url = db_url
        self.versions_dir = Path(versions_dir)
    
    def drop_alembic_version_table(self) -> None:
        """alembic_version テーブルを削除"""
        engine = create_engine(self.db_url)
        
        with engine.connect() as conn:
            # テーブルが存在するか確認
            result = conn.execute(text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='alembic_version'"
            ))
            
            if result.fetchone():
                conn.execute(text("DROP TABLE alembic_version"))
                conn.commit()
                print("✓ Dropped alembic_version table")
            else:
                print("✓ alembic_version table does not exist")
    
    def delete_migration_files(self) -> None:
        """マイグレーションファイルを削除"""
        if not self.versions_dir.exists():
            print(f"✓ Versions directory does not exist: {self.versions_dir}")
            return
        
        deleted_count = 0
        for file in self.versions_dir.glob("*.py"):
            # __init__.py は保持
            if file.name == "__init__.py":
                continue
            
            file.unlink()
            deleted_count += 1
            print(f"  - Deleted: {file.name}")
        
        if deleted_count > 0:
            print(f"✓ Deleted {deleted_count} migration file(s)")
        else:
            print("✓ No migration files to delete")
        
        # __pycache__ も削除
        pycache = self.versions_dir / "__pycache__"
        if pycache.exists():
            import shutil
            shutil.rmtree(pycache)
            print("✓ Deleted __pycache__")
```

### 4. CLI スクリプト

**責務**: コマンドラインからの実行

```python
# repom/scripts/alembic_init.py
"""Alembic の初回セットアップスクリプト"""
import argparse
from pathlib import Path
from repom.alembic.setup import AlembicSetup

def main():
    parser = argparse.ArgumentParser(
        description="Initialize Alembic for a repom project"
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory (default: current directory)"
    )
    parser.add_argument(
        "--version-locations",
        help="Version locations (default: alembic/versions)"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files"
    )
    
    args = parser.parse_args()
    
    setup = AlembicSetup(
        project_root=args.project_root,
        version_locations=args.version_locations
    )
    
    print("Initializing Alembic...")
    setup.create_alembic_ini(overwrite=args.overwrite)
    setup.create_version_directory()
    print("\n✓ Alembic initialized successfully")
    print(f"  - alembic.ini: {Path(args.project_root) / 'alembic.ini'}")
    print(f"  - versions dir: {setup.versions_dir}")
    print(f"\nNote: env.py and script.py.mako are provided by repom.")

if __name__ == "__main__":
    main()
```

```python
# repom/scripts/alembic_reset.py
"""Alembic マイグレーションのリセットスクリプト"""
import argparse
from repom.alembic.setup import AlembicSetup

def main():
    parser = argparse.ArgumentParser(
        description="Reset Alembic migrations (drop table and delete files)"
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory (default: current directory)"
    )
    parser.add_argument(
        "--no-drop-table",
        action="store_true",
        help="Do not drop alembic_version table"
    )
    parser.add_argument(
        "--no-delete-files",
        action="store_true",
        help="Do not delete migration files"
    )
    
    args = parser.parse_args()
    
    setup = AlembicSetup(project_root=args.project_root)
    
    print("Resetting Alembic migrations...")
    setup.reset_migrations(
        drop_table=not args.no_drop_table,
        delete_files=not args.no_delete_files
    )
    print("✓ Alembic migrations reset successfully")

if __name__ == "__main__":
    main()
```

### 5. pyproject.toml へのスクリプト登録

```toml
[tool.poetry.scripts]
# 既存のスクリプト...
alembic_init = "repom.scripts.alembic_init:main"
alembic_reset = "repom.scripts.alembic_reset:main"
```

---

## 影響範囲

### 変更が必要なファイル

**新規作成**:
- `repom/alembic/__init__.py`
- `repom/alembic/setup.py`
- `repom/alembic/templates.py`
- `repom/alembic/reset.py`
- `repom/scripts/alembic_init.py`
- `repom/scripts/alembic_reset.py`

**更新**:
- `pyproject.toml` - 新しいスクリプトを追加
- `tests/behavior_tests/test_migration_no_id.py` - AlembicSetup を使用するようリファクタ
- `tests/behavior_tests/test_alembic_env_loads_models.py` - AlembicSetup を使用
- `docs/guides/features/alembic_migration_guide.md` - 新機能の説明を追加

### 削除可能なコード

- `test_migration_no_id.py` 内の `_get_alembic_ini_content()` (約60行)
- `test_migration_no_id.py` 内の `_get_env_py_content()` (約40行) - **repom が提供するため不要に**
- `test_migration_no_id.py` 内の `_get_mako_content()` (約30行) - **repom が提供するため不要に**
- 同様のコードが他のテストにも存在する場合は削除

**削減見込み**: 約150-200行（env.py と script.py.mako の生成コードが不要になるため）

---

## 実装計画

### Phase 1: コア実装（3-4時間）

1. **repom/alembic/templates.py を作成**
   - `generate_alembic_ini()` 実装のみ
   - **注意**: env.py と script.py.mako は repom が既に提供

2. **repom/alembic/reset.py を作成**
   - `drop_alembic_version_table()` 実装
   - `delete_migration_files()` 実装

3. **repom/alembic/setup.py を作成**
   - `AlembicSetup` クラス実装
   - 各メソッドの実装

### Phase 2: CLI スクリプト（1-2時間）

4. **repom/scripts/alembic_init.py を作成**
   - argparse でコマンドライン引数を処理
   - AlembicSetup を使用

5. **repom/scripts/alembic_reset.py を作成**
   - argparse でコマンドライン引数を処理
   - AlembicSetup を使用

6. **pyproject.toml を更新**
   - スクリプトエントリを追加

### Phase 3: テストのリファクタリング（2-3時間）

7. **test_migration_no_id.py をリファクタ**
   - AlembicSetup を使用するよう書き換え
   - 重複コードを削除

8. **test_alembic_env_loads_models.py をリファクタ**
   - AlembicSetup を使用するよう書き換え

### Phase 4: ドキュメント更新（1時間）

9. **alembic_migration_guide.md を更新**
   - 新機能の使い方セクションを追加
   - リセット方法を追加

### Phase 5: テストとバリデーション（2時間）

10. **ユニットテストを作成**
    - `test_alembic_setup.py`
    - `test_alembic_templates.py`
    - `test_alembic_reset.py`

11. **全テストを実行**
    - 既存テストが壊れていないか確認
    - 新しい機能が正しく動作するか確認

**総見積もり**: 9-12時間

---

## テスト計画

### 1. ユニットテスト

```python
# tests/unit_tests/test_alembic_setup.py
def test_alembic_setup_creates_alembic_ini(tmp_path):
    """AlembicSetup が alembic.ini を正しく作成する"""
    setup = AlembicSetup(project_root=tmp_path)
    setup.create_alembic_ini()
    
    assert (tmp_path / "alembic.ini").exists()
    
    # env.py と script.py.mako は repom が提供するため生成しない
    # 外部プロジェクトでは script_location で repom の alembic を参照

def test_alembic_setup_does_not_overwrite_existing_ini(tmp_path):
    """既存の alembic.ini を上書きしない（安全性）"""
    setup = AlembicSetup(project_root=tmp_path)
    
    # 最初に作成
    setup.create_alembic_ini()
    original_content = (tmp_path / "alembic.ini").read_text()
    
    # 再実行（overwrite=False）
    setup.create_alembic_ini(overwrite=False)
    assert (tmp_path / "alembic.ini").read_text() == original_content

def test_alembic_setup_creates_version_directory(tmp_path):
    """version_locations ディレクトリが正しく作成される"""
    setup = AlembicSetup(project_root=tmp_path)
    setup.create_version_directory()
    
    assert setup.versions_dir.exists()
    assert (setup.versions_dir / "__init__.py").exists()

def test_alembic_reset_drops_table(tmp_path):
    """alembic_version テーブルが削除される"""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    
    # テーブルを作成
    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        conn.commit()
    
    # リセット
    reset = AlembicReset(db_url=db_url, versions_dir=tmp_path)
    reset.drop_alembic_version_table()
    
    # テーブルが削除されたことを確認
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
        ))
        assert result.fetchone() is None
```

### 2. インテグレーションテスト

```python
# tests/integration_tests/test_alembic_setup_integration.py
def test_full_alembic_workflow_with_setup(tmp_path):
    """AlembicSetup を使った完全なワークフロー"""
    setup = AlembicSetup(
        project_root=tmp_path,
        db_url=f"sqlite:///{tmp_path}/test.db"
    )
    
    # 初期化（alembic.ini と version_locations のみ）
    setup.create_alembic_ini()
    setup.create_version_directory()
    
    # マイグレーション生成
    alembic_cfg = setup.get_alembic_config()
    command.revision(alembic_cfg, message="test", autogenerate=True)
    
    # マイグレーションファイルが作成されたことを確認
    migration_files = list(setup.versions_dir.glob("*.py"))
    assert len([f for f in migration_files if f.name != "__init__.py"]) > 0
    
    # リセット
    setup.reset_migrations()
    
    # ファイルとテーブルが削除されたことを確認
    migration_files = list(setup.versions_dir.glob("*.py"))
    assert len([f for f in migration_files if f.name != "__init__.py"]) == 0
```

### 3. 既存テストの動作確認

- `test_migration_no_id.py` - リファクタ後も正しく動作するか
- `test_alembic_env_loads_models.py` - リファクタ後も正しく動作するか

---

## 完了基準

- ✅ `repom/alembic/` 以下に setup.py, templates.py, reset.py が実装されている
- ✅ `repom/scripts/` 以下に alembic_init.py, alembic_reset.py が実装されている
- ✅ `poetry run alembic_init` コマンドが動作する（alembic.ini と version_locations のみ作成）
- ✅ `poetry run alembic_reset` コマンドが動作する
- ✅ test_migration_no_id.py が AlembicSetup を使用してリファクタされている（env.py, script.py.mako の生成コードが削除されている）
- ✅ test_alembic_env_loads_models.py が AlembicSetup を使用してリファクタされている
- ✅ 新規ユニットテストが10個以上追加され、全てパスする
- ✅ 既存の全テストがパスする（回帰テスト）
- ✅ alembic_migration_guide.md に新機能のセクションが追加されている
- ✅ 重複コードが150-200行削減されている（alembic.ini 生成のみに簡素化）
- ✅ 既存ファイルの上書き防止機能が動作する（overwrite=False がデフォルト）

---

## 関連ドキュメント

- **現在の実装**:
  - `alembic/env.py` - 既存の環境設定
  - `alembic.ini` - 既存の設定ファイル
  - `tests/behavior_tests/test_migration_no_id.py` - リファクタ対象

- **ガイド**:
  - `docs/guides/features/alembic_migration_guide.md` - 更新対象

- **技術ドキュメント**:
  - `docs/technical/alembic_version_locations_limitation.md` - version_locations の制約

- **関連 Issue**:
  - Issue #008: Alembic マイグレーションファイルの保存場所制御

---

## 備考

### なぜこの実装が必要か

1. **DRY 原則**: 重複コードを排除し、メンテナンス性を向上
2. **テスト容易性**: テストでのマイグレーション管理を簡素化
3. **開発体験**: 開発時のマイグレーションリセットを容易に
4. **外部プロジェクト**: 初回セットアップを自動化

### 設計判断

- **repom/alembic/ に配置**: Alembic 関連の機能をまとめる
- **3つのモジュールに分割**: 責務を明確にし、テスト容易性を向上
  - `setup.py`: 統合インターフェース
  - `templates.py`: テンプレート管理
  - `reset.py`: リセット機能
- **CLI スクリプト提供**: スクリプトとしても使えるようにする

### 今後の拡張可能性

- PostgreSQL 対応（alembic_version テーブル削除の SQL を調整）
- テンプレートのカスタマイズ機能
- マイグレーション履歴のバックアップ機能

---

**最終更新**: 2026-02-04
