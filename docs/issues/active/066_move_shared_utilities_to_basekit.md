# Issue #66: `repom/_/` 共有ユーティリティを basekit へ移管

**ステータス**: 🔴 未着手

**作成日**: 2026-05-19

**優先度**: 中

## 問題の説明

`repom/_/` 配下の 3 ファイルはいずれもフレームワーク非依存の汎用ユーティリティで、
repom 固有の概念（モデル / リポジトリ / SQLAlchemy など）に依存していない。

- [repom/_/discovery.py](../../../repom/_/discovery.py)
  パッケージ・モジュールの動的インポートと失敗集約。外部依存は標準ライブラリのみ。
- [repom/_/docker_compose.py](../../../repom/_/docker_compose.py)
  `DockerService` / `DockerVolume` / `DockerComposeGenerator`。完全に純粋なユーティリティ。
- [repom/_/docker_manager.py](../../../repom/_/docker_manager.py)
  `DockerCommandExecutor`、`DockerManager` 基盤、`print_message` / `validate_compose_file_exists` / `format_connection_info`。
  唯一 `from repom.config import config` に依存し、`config.data_path` を `get_compose_dir()` から参照している。

これらは basekit（[C:/Users/jj/Desktop/workspace_main/projects/basekit](C:/Users/jj/Desktop/workspace_main/projects/basekit)）に移すのが自然で、
basekit を依存する他プロジェクト（fast-domain など）でも再利用できる。
互換性維持の制約はなく、import パスを完全に切り替える前提で進めてよい。

## 提案される解決策

### 移管先と公開 API（basekit 側）

basekit はソースを `src/basekit/` 直下にフラットに置く構成なので、サブパッケージを 1 つ作るのではなく
**機能ごとにモジュール 1 ファイル** を追加する形に揃える。

```
src/basekit/
├── __init__.py
├── config_hook.py
├── logging.py
├── discovery.py       # NEW (= repom/_/discovery.py をそのまま移植)
├── docker_compose.py  # NEW (= repom/_/docker_compose.py をそのまま移植)
└── docker_manager.py  # NEW (= repom/_/docker_manager.py を再設計して移植)
```

import 経路は：

```python
from basekit.discovery import import_from_packages, DiscoveryError, ...
from basekit.docker_compose import DockerComposeGenerator, DockerService, DockerVolume
from basekit.docker_manager import (
    DockerManager,
    DockerCommandExecutor,
    print_message,
    validate_compose_file_exists,
    format_connection_info,
)
```

### モジュール別の設計方針

#### 1. `basekit.discovery`（無変更移植）

- 現状の API（`normalize_paths` / `DiscoveryFailure` / `DiscoveryError` /
  `validate_package_security` / `import_packages` / `import_from_directory` /
  `import_package_directory` / `import_from_packages`）をそのまま移す。
- 外部依存なし。テストも `tests/unit_tests/test_discovery_helpers.py` を basekit 側へ移植可能。

#### 2. `basekit.docker_compose`（無変更移植）

- `DockerService` / `DockerVolume` / `DockerComposeGenerator` をそのまま移す。
- 単体テスト `tests/unit_tests/test_docker_compose.py` を basekit へ移植。

#### 3. `basekit.docker_manager`（**再設計が必要**）

現状の `DockerManager` は `from repom.config import config` をモジュールトップで import し、
`get_compose_dir()` 内で `Path(config.data_path) / self.SERVICE_NAME` を組み立てている。
basekit には repom への参照を持たせないため、ここを設定注入（DI）方式に変える。

**変更点 (A): `repom.config` への依存を切る**

[repom/_/docker_manager.py:30](../../../repom/_/docker_manager.py#L30) のモジュールレベル import を廃止し、
`DockerManager.__init__` で `data_path` を受け取る（または `basekit.Config` を受け取る）。

```python
# basekit/docker_manager.py
from basekit.config_hook import Config

class DockerManager(ABC):
    SERVICE_NAME: ClassVar[str]
    INIT_SUBDIR: ClassVar[str]
    GENERATE_COMMAND: ClassVar[str]

    def __init__(self, *, data_path: str | Path, ...):
        self._data_path = Path(data_path)

    def get_compose_dir(self) -> Path:
        compose_dir = self._data_path / self.SERVICE_NAME
        compose_dir.mkdir(parents=True, exist_ok=True)
        return compose_dir
```

repom 側のサブクラスは `super().__init__(data_path=config.data_path)` を呼ぶ形に変える。
（repom の `RepomConfig` は basekit の `Config` を継承しているので `data_path` プロパティは利用可能。）

**変更点 (B): `GENERATE_COMMAND` のヒント文言を抽象化**

現状 `get_compose_file_path()` のエラーメッセージは
`"Hint: Run 'uv run {self.GENERATE_COMMAND}' first"` と repom の CLI 命名前提のフォーマットになっている。
basekit に置く以上、`uv run` 固定はやめてサブクラス側で自由に上書きできるよう、
クラス変数 `GENERATE_COMMAND_HINT` を別途切り出すか、`hint_message` メソッドに分離する。

```python
class DockerManager(ABC):
    GENERATE_COMMAND: ClassVar[str]

    def get_generate_hint(self) -> str:
        return f"Hint: Run 'uv run {self.GENERATE_COMMAND}' first"
```

repom 側サブクラスは既定実装を使うだけで現状と等価。fast-domain など他プロジェクトでは
オーバーライドできる余地を残す。

**変更点 (C): メッセージ文言の英語化（軽微）**

`validate_compose_file_exists()` の中に日本語文字列
（"docker-compose.generated.yml が見つかりません" / "先に '...' を実行してください"）が混ざっている。
basekit は汎用パッケージなので英語に揃える（既存ガイドの和訳は repom 側ガイドに残す）。

**変更点 (D): `print_message` の絵文字フォールバック（変更なし）**

cp932 対策の `try / except UnicodeEncodeError` 分岐は basekit でもそのまま採用する。

### repom 側の差し替え作業

互換シムは設けず、`from repom._.X` → `from basekit.X` に一括置換し、
`repom/_/discovery.py` / `repom/_/docker_compose.py` / `repom/_/docker_manager.py` を削除する。
`repom/_/__init__.py` も他に内容がなければ削除する（要確認）。

差し替え対象（grep 既調査済）:

- `repom/utility.py:7-17`（discovery）
- `repom/postgres/manage.py:14-15`（docker_compose, docker_manager）
- `repom/redis/manage.py:14-15`（同上）
- `repom/scripts/repom_info.py`
- `repom/scripts/db_backup.py`
- `repom/scripts/db_restore.py`
- `tests/unit_tests/test_auto_import_models.py`
- `tests/unit_tests/test_discovery_helpers.py`
- `tests/unit_tests/test_docker_compose.py`
- `tests/unit_tests/test_redis_manager.py`
- `tests/unit_tests/docker_manager/` 配下 4 ファイル
- `tests/behavior_tests/test_type_checking_import_order.py`
- `tests/behavior_tests/test_type_checking_detailed.py`
- `tests/behavior_tests/test_circular_import.py`
- `tests/behavior_tests/test_circular_import_solutions.py`

なお `repom/_/docker_manager.py:339` の `get_compose_file_path()` は basekit に移ったあと、
repom 側 `PostgresManager` / `RedisManager` に `data_path` を渡すコンストラクタ変更が必要になる。

### ガイドの差し替え

- [docs/guides/features/discovery_guide.md](../../guides/features/discovery_guide.md)
- [docs/guides/features/docker_compose_guide.md](../../guides/features/docker_compose_guide.md)
- [docs/guides/features/docker_manager_guide.md](../../guides/features/docker_manager_guide.md)

これらの import 例を `basekit.X` 系に書き換える。basekit リポジトリにもガイドを移植するかは
別途検討（最小では repom 側で `basekit に移管された` 旨だけ追記し、本体は basekit に置く）。

### basekit 側のテスト

repom 側のテストのうち純粋な単体テストは basekit に移植する：

- `tests/unit_tests/test_discovery_helpers.py` → basekit `tests/unit_tests/test_discovery.py`
- `tests/unit_tests/test_docker_compose.py` → basekit `tests/unit_tests/test_docker_compose.py`
- `tests/unit_tests/docker_manager/test_docker_command_executor.py`
- `tests/unit_tests/docker_manager/test_utility_functions.py`
- `tests/unit_tests/docker_manager/test_docker_manager.py`（`config` 依存解消に伴う書き換えあり）

repom 固有のもの（`test_redis_manager.py`、`docker_manager/test_docker_manager_integration.py` のうち
`config` と結合しているもの、`test_auto_import_models.py` 等）は repom 側に残し、import パスだけ
`basekit.X` に切り替える。

### basekit のバージョン pin 更新

[pyproject.toml:66-67](../../../pyproject.toml#L66-L67) の `[tool.uv.sources]` で basekit を
git の固定 rev 指定にしている：

```toml
[tool.uv.sources]
basekit = { git = "https://github.com/jjjun/basekit.git", rev = "ca97f2dba52120fa28c543678830d69b9ee608d9" }
```

basekit 側で本件の変更を push したあと、新しい rev に上げる必要がある。

## 影響範囲

### 削除
- `repom/_/discovery.py`
- `repom/_/docker_compose.py`
- `repom/_/docker_manager.py`
- 上が空になれば `repom/_/__init__.py` および `repom/_/` ディレクトリ自体

### 修正
- `repom/utility.py`
- `repom/postgres/manage.py` / `repom/redis/manage.py`
  （`super().__init__(data_path=...)` 呼び出し追加）
- `repom/scripts/repom_info.py` / `db_backup.py` / `db_restore.py`
- 各種テスト（上述）
- ガイド 3 本（上述）
- `pyproject.toml` の basekit `rev` 更新
- `CLAUDE.md` に `repom/_/` の記述があれば整理（**現時点で記述なしを確認**）

### basekit 側追加
- `src/basekit/discovery.py`
- `src/basekit/docker_compose.py`
- `src/basekit/docker_manager.py`
- 各モジュールの単体テスト
- `src/basekit/__init__.py` で公開 API を再エクスポート（任意。利用側は基本 `from basekit.X` 経由なので必須ではない）
- basekit 側ガイドの追加（任意）

## 実装計画

### Phase 1: basekit 側で 3 モジュールを追加（基盤作り）

1. `src/basekit/discovery.py` を `repom/_/discovery.py` から **そのままコピー** で作成
2. `src/basekit/docker_compose.py` を同様に **そのままコピー** で作成
3. `src/basekit/docker_manager.py` を **再設計** で作成
   - モジュールトップの `from repom.config import config` を削除
   - `DockerManager.__init__(self, *, data_path)` を追加し `self._data_path` を保持
   - `get_compose_dir()` を `self._data_path` ベースに修正
   - `get_generate_hint()` メソッドを切り出し
   - `validate_compose_file_exists()` の日本語文言を英語化
4. basekit `tests/unit_tests/` に 3 モジュールぶんのテストを追加
   - repom 側の対応テストをコピーし、`from repom._.X` → `from basekit.X` に変換
   - `DockerManager` テストの `config` 依存箇所は `data_path=tmp_path` 注入に書き換え
5. basekit リポジトリで `uv run pytest` 緑、コミット & push、新しい `rev` を取得

### Phase 2: repom 側を basekit に差し替え

6. `pyproject.toml` の `[tool.uv.sources]` で basekit を新 rev に更新
7. `uv lock` / `uv sync` で basekit 更新を反映
8. 一括置換:
   - `from repom._.discovery import ...` → `from basekit.discovery import ...`
   - `from repom._.docker_compose import ...` → `from basekit.docker_compose import ...`
   - `from repom._ import docker_manager as dm` → `from basekit import docker_manager as dm`
   - patch ターゲット `"repom._.docker_manager.XXX"` → `"basekit.docker_manager.XXX"`
9. `PostgresManager` / `RedisManager` の `__init__` に
   `super().__init__(data_path=config.data_path)` を追加
10. `repom/_/discovery.py` / `repom/_/docker_compose.py` / `repom/_/docker_manager.py` を削除
11. `repom/_/__init__.py` の中身を確認のうえ、空または不要なら削除
12. `uv run pytest` で unit / behavior 双方が緑であることを確認

### Phase 3: ドキュメント・ガイド更新

13. `docs/guides/features/discovery_guide.md` / `docker_compose_guide.md` / `docker_manager_guide.md`
    の import 例を `basekit.X` に修正
14. 「basekit に移管されました」旨を冒頭に追記
15. basekit リポジトリにもガイドの簡易版を置く（任意）

### Phase 4: 完了処理

16. Issue を `completed/066_move_shared_utilities_to_basekit.md` に移動
17. `docs/issues/README.md` を更新
18. コミット: `docs(issue): Complete issue #066 - Move shared utilities to basekit`

## テスト計画

- basekit 側
  - `uv run pytest` で discovery / docker_compose / docker_manager のユニットテスト全パス
  - `DockerManager` の `data_path` 注入が機能していることを `tmp_path` 経由で確認
- repom 側
  - `uv run pytest tests/unit_tests` 全パス
  - `uv run pytest tests/behavior_tests` 全パス
  - `uv run postgres_generate` / `uv run postgres_start` / `uv run redis_generate` を手動で実行し、
    `data_path/postgres/` / `data_path/redis/` 配下に compose ファイルが生成され、コンテナが起動することを確認
  - `uv run repom_info` が PostgreSQL 接続情報を表示できることを確認

## リスク・留意点

- **`pyproject.toml` の rev 更新タイミング**: basekit 側がマージされていない状態で repom 側を進めると
  uv が新しいモジュールを解決できない。Phase 1 を完了し basekit に commit/push してから Phase 2 に入る。
- **`repom._` の patch ターゲット書き換え漏れ**: テストの `unittest.mock.patch` 文字列は
  grep で網羅しているが、置換時に追加ファイルがないか最終確認する。
- **fast-domain など外部利用者**: 現状 `repom._.docker_manager` を直接 import している外部プロジェクトが
  あれば壊れる（要 grep）。互換性を考慮しない方針なので壊してよいが、影響範囲は別途共有する。
- **`get_compose_dir()` の data_path 解決**: basekit 側で `data_path` を None のまま渡されたケースの
  扱いを設計（`ValueError` を投げるか、`Path.cwd() / "data"` を既定にするか）を決める。
  repom 側からは常に `config.data_path` を渡すので問題は出ないが、basekit 単体利用者向けの
  ガード仕様を文書化する。

## 関連リソース

- 既存 repom 側ファイル: [repom/_/discovery.py](../../../repom/_/discovery.py),
  [repom/_/docker_compose.py](../../../repom/_/docker_compose.py),
  [repom/_/docker_manager.py](../../../repom/_/docker_manager.py)
- basekit リポジトリ: [C:/Users/jj/Desktop/workspace_main/projects/basekit](C:/Users/jj/Desktop/workspace_main/projects/basekit)
- 既存テスト: `tests/unit_tests/test_discovery_helpers.py`,
  `tests/unit_tests/test_docker_compose.py`, `tests/unit_tests/docker_manager/`
- 既存ガイド: [docs/guides/features/discovery_guide.md](../../guides/features/discovery_guide.md),
  [docs/guides/features/docker_compose_guide.md](../../guides/features/docker_compose_guide.md),
  [docs/guides/features/docker_manager_guide.md](../../guides/features/docker_manager_guide.md)
- 関連完了 issue:
  [completed/025_generic_package_discovery_infrastructure.md](../completed/025_generic_package_discovery_infrastructure.md),
  [completed/038_postgresql_container_customization.md](../completed/038_postgresql_container_customization.md),
  [completed/040_docker_management_base_infrastructure.md](../completed/040_docker_management_base_infrastructure.md),
  [completed/062_postgres_redis_compose_dir_unification.md](../completed/062_postgres_redis_compose_dir_unification.md)
