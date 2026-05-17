# Issue #058: Poetry から uv へのパッケージマネージャ移行

**ステータス**: 🔴 未着手

**作成日**: 2026-05-17

**優先度**: 中

## 問題の説明

repom は現在 Poetry を使って依存解決・仮想環境管理・スクリプト実行を行っている。
高速化・モダン化の観点から `uv` (astral-sh/uv) への移行を行いたい。

### 現状

- `pyproject.toml`
  - `[project]` テーブル自体は **PEP 621 準拠で記述済み** (Issue 経由で移行済)。依存関係・optional-dependencies・scripts は既に標準形。
  - Poetry 固有の残存箇所:
    - `[tool.poetry]` — `packages = [{ include = "repom" }]`
    - `[tool.poetry.group.dev.dependencies]` — pytest 系・fastapi・httpx などの開発依存
    - `[build-system]` — `requires = ["poetry-core"]`, `build-backend = "poetry.core.masonry.api"`
- `poetry.lock` (1449 行) が存在し、`uv.lock` は未生成
- `_.python-version` に `3.12.8`（ファイル名先頭にアンダースコアがあり、`uv` が認識する `.python-version` と異なる）
- `.vscode/tasks.json` 内の 9 タスク全てが `poetry run ...` を呼ぶ
- ドキュメント類で `poetry` への参照が多数:
  - `README.md` / `CLAUDE.md` / `AGENTS.md` / `.github/copilot-instructions.md`
  - `docs/guides/**/*.md` の多くで `poetry run pytest`, `poetry run db_create` などの例示
  - `docs/issues/completed/*.md` の過去履歴（参照は残しても問題なし）
- Python ソース内の文字列（docstring / エラーメッセージ）でも `poetry run` を案内しているものがある:
  - `repom/postgres/manage.py`, `repom/redis/manage.py`, `repom/_/docker_manager.py`
  - `repom/scripts/db_backup.py`, `repom/scripts/db_restore.py`, `repom/scripts/db_sync_master.py`
  - `repom/config_hook.py`, `repom/logging.py`, `repom/testing.py`
- CI: `.github/workflows/` は存在しない（移行コストは限定的）

## 提案される解決策

uv (PEP 621 + PEP 735) ベースに置き換える。

1. **`pyproject.toml` を uv ネイティブに修正**
   - `[tool.poetry]` セクションを削除
   - dev 依存を PEP 735 の `[dependency-groups]` に移行 (`[dependency-groups].dev = [...]`)
   - `[build-system]` を `hatchling` ベースに変更（推奨デフォルト。`uv_build` でも可だが互換性重視で hatchling）
     ```toml
     [build-system]
     requires = ["hatchling"]
     build-backend = "hatchling.build"

     [tool.hatch.build.targets.wheel]
     packages = ["repom"]
     ```
   - 必要に応じて `[tool.uv]` を追加（特になければ省略可）
   - Caret 表記 (`^0.3.0` 等) は dev 依存の移行時に PEP 440 形式 (`>=0.3.0,<0.4.0` など) に置換
2. **ロックファイル切り替え**
   - `uv lock` を実行して `uv.lock` を生成
   - `poetry.lock` を削除
3. **Python バージョンファイル整理**
   - `_.python-version` を `.python-version` にリネーム（uv が自動で読み取れる形式に揃える）
4. **VSCode タスク更新**
   - `.vscode/tasks.json` の `poetry run ...` を `uv run ...` に置換（9 タスク）
5. **ドキュメント更新**
   - `README.md` / `CLAUDE.md` / `AGENTS.md` / `.github/copilot-instructions.md` のセットアップ・コマンド例を `uv` ベースに書き換え
   - `docs/guides/**/*.md` 内のコマンド例を一括更新
   - `poetry install --extras X` → `uv sync --extra X`
   - `poetry install --sync` → `uv sync`
   - `poetry add ...` → `uv add ...`
6. **ソース内文字列の更新**
   - docstring とエラーメッセージのヒント表示を `uv run ...` に修正（上記 9 ファイル）
7. **動作検証**
   - `uv sync` で環境再構築
   - `uv run pytest tests/unit_tests tests/behavior_tests` が全てパスすることを確認
   - 主要スクリプト (`uv run repom_info`, `uv run db_create`, `uv run alembic current` 等) が動作することを確認
   - PostgreSQL/Redis 関連の extras (`uv sync --extra postgres` 等) のインストールを確認

## 影響範囲

### 設定ファイル（必須変更）
- `pyproject.toml` — `[tool.poetry]`, `[tool.poetry.group.dev.dependencies]`, `[build-system]`
- `poetry.lock` → 削除、`uv.lock` を新規生成
- `_.python-version` → `.python-version`
- `.vscode/tasks.json` — 9 タスク

### ソースコード（文字列のみ）
- `repom/postgres/manage.py`
- `repom/redis/manage.py`
- `repom/_/docker_manager.py`
- `repom/scripts/db_backup.py`
- `repom/scripts/db_restore.py`
- `repom/scripts/db_sync_master.py`
- `repom/config_hook.py`
- `repom/logging.py`
- `repom/testing.py`

### ドキュメント（多数）
- `README.md`, `CLAUDE.md`, `AGENTS.md`
- `.github/copilot-instructions.md`
- `docs/guides/**/*.md`（テスト・PostgreSQL・Redis・Alembic ガイド等）

### 影響を受けない
- 機能ロジック・モデル・リポジトリ・テスト本体・Alembic マイグレーション
- 公開 API、entry point 名称（`[project.scripts]` はそのまま流用される）

## 実装計画

### Phase 1: pyproject.toml の刷新
1. `[tool.poetry]` と `[tool.poetry.group.dev.dependencies]` を削除し、`[dependency-groups]` の `dev` に移行
2. caret 制約 (`^X.Y.Z`) を PEP 440 形式に変換
3. `[build-system]` を hatchling に切り替え、`[tool.hatch.build.targets.wheel]` で `repom` パッケージを指定
4. `uv lock` を実行し `uv.lock` を生成
5. `poetry.lock` を削除

### Phase 2: 環境ファイル・タスク・ソース文字列
1. `_.python-version` → `.python-version` にリネーム
2. `.vscode/tasks.json` の `poetry run` を `uv run` に置換
3. ソース内 docstring / エラーメッセージ内 `poetry run` を `uv run` に置換（機能には影響なし）

### Phase 3: ドキュメント一括更新
1. `README.md` のセットアップ・コマンドリファレンス更新
2. `CLAUDE.md` / `AGENTS.md` 更新（Package Manager 表記含む）
3. `.github/copilot-instructions.md` 更新
4. `docs/guides/**/*.md` のコマンド例一括置換

### Phase 4: 検証
1. `uv sync` でクリーンインストール
2. `uv sync --extra postgres --extra redis --extra async-all` で extras 検証
3. `uv run pytest tests/unit_tests tests/behavior_tests` で全テストパス
4. `uv run repom_info` などのスクリプトが期待通り起動することを確認
5. `uv build` で wheel が生成できること（hatchling 移行の確認）

## テスト計画

- **回帰**: 既存の unit/behavior テストが 100% パスすること（現状ベースライン: 831 passed, 10 skipped）
- **エントリポイント**: `[project.scripts]` の各 console script が `uv run <name>` で起動できること
- **extras**: `uv sync --extra postgres` / `--extra postgres-async` / `--extra redis` / `--extra async` / `--extra async-all` がそれぞれ正常にインストールされること
- **ビルド**: `uv build` で wheel が生成され、生成物に `repom/` パッケージが含まれること
- **VSCode タスク**: タスク一覧の各タスクが手動実行で成功すること

## 移行時の注意点

- `poetry install` で `dev` グループは自動インストールだったが、`uv sync` は `[dependency-groups].dev` も既定でインストールする（`--no-dev` で除外）。挙動差を CLAUDE.md に明記する
- `poetry install --extras X` 相当は `uv sync --extra X`（`uv add --optional X pkg` で追加）
- 既存ユーザーが手元に持つ `.venv` は `uv` でも `.venv` を使うため互換性あり。ただし lock の解決が変わるためクリーンアップ後に `uv sync` 推奨
- `alembic.ini` / `alembic/env.py` は package manager 非依存のためそのまま

## 関連リソース

- [uv ドキュメント](https://docs.astral.sh/uv/)
- [PEP 735 — Dependency Groups in pyproject.toml](https://peps.python.org/pep-0735/)
- Issue #003 経由で `pyproject.toml` は既に PEP 621 化済み（コミット `3434b93`）
- 現状の `pyproject.toml` Poetry 依存箇所: 45-46 行 (`[tool.poetry]`), 48-56 行 (dev deps), 58-60 行 (`[build-system]`)
