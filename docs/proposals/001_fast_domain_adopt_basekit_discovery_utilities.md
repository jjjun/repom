# Proposal #001: fast-domain adopt basekit discovery utilities

## メタデータ

| 項目 | 値 |
|------|---|
| **ID** | 001 |
| **対象プロジェクト / パッケージ** | fast-domain |
| **種別** | breaking / dependency alignment |
| **ステータス** | draft |
| **作成日** | 2026-05-19 |
| **最終更新** | 2026-05-19 |

---

## 背景

repom issue `066_move_shared_utilities_to_basekit` の対応で、repom にあった次の汎用ユーティリティは basekit へ移設された。

- `repom._.discovery` -> `basekit.discovery`
- `repom._.docker_compose` -> `basekit.docker_compose`
- `repom._.docker_manager` -> `basekit.docker_manager`

repom 側では旧 private module を削除済みで、Docker 管理処理は repom の public API から引き続き利用できるように `repom.postgres.manage` / `repom.redis.manage` の内部で basekit を参照する形に変わっている。

fast-domain は `repom` を `submod/repom` の editable path dependency として利用しているため、submodule を repom commit `70f3198` 以降へ更新すると、fast-domain 側に残っている `repom._.discovery` 直接 import が壊れる。

---

## 現状と困りごと

調査時点の fast-domain は作業ツリー clean。

`pyproject.toml` では basekit が古い初期 commit に固定されている。

```toml
[tool.uv.sources]
basekit = { git = "https://github.com/jjjun/basekit.git", rev = "ca97f2dba52120fa28c543678830d69b9ee608d9" }
repom = { path = "./submod/repom", editable = true }
```

`uv.lock` も同じ basekit rev を参照している。

fast-domain の `submod/repom` は調査時点で `199e63c` を指しており、今回の repom commit `70f3198` より前の状態である。

ソースとテストには `repom._.discovery` への直接依存が残っている。

- `src/fast_domain/routes.py`
- `src/fast_domain/invoke/config.py`
- `src/fast_domain/invoke/loader.py`
- `src/fast_domain/config.py`
- `src/fast_domain/assets/config.py`
- `tests/unit_tests/test_model_auto_import.py`

一方で `repom._.docker_compose` / `repom._.docker_manager` への直接 import は、`src` / `tests` / active docs / guides の範囲では見つからなかった。

fast-domain の Docker 起動連携は次の public repom API を経由している。

- `src/fast_domain/db/bootstrap.py`: `repom.postgres.manage.ensure_running`
- `src/fast_domain/arq/bootstrap.py`: `repom.redis.manage.ensure_running`

このため Docker 系は fast-domain で basekit へ直接置換する必要はなく、repom submodule と basekit rev を同時に更新できればよい。

---

## 提案内容

fast-domain 側で次の順に対応する。

1. basekit の GitHub rev pin を、`discovery` / `docker_compose` / `docker_manager` を含む commit へ更新する。

   ```toml
   basekit = { git = "https://github.com/jjjun/basekit.git", rev = "ccdf6f3fbcfee5e0b93b27e294ea6507af408dc2" }
   ```

2. `submod/repom` を repom commit `70f3198` 以降へ更新する。

3. `repom._.discovery` import を `basekit.discovery` import に置き換える。

   ```python
   from basekit.discovery import DiscoveryError, import_from_packages, normalize_paths
   ```

4. lockfile を更新する。

   ```bash
   uv lock --upgrade-package basekit
   uv sync
   ```

5. 必要なら repom と同様に VSCode task / script を追加し、basekit rev pin 更新をコマンド化する。

   fast-domain は basekit と repom submodule の組み合わせに依存するため、手動更新時に片方だけ古いままになりやすい。少なくとも `basekit` の rev 更新は task 化しておくと事故を減らせる。

---

## 期待する効果

- repom の private module 削除後も fast-domain の router / task / model discovery が動く。
- shared utility の所有元が basekit に揃い、fast-domain から repom の private module へ依存しなくなる。
- Docker 起動連携は fast-domain 側の public repom API 利用を維持できるため、fast-domain の責務を増やさずに済む。

---

## repom 側の影響

repom 側の追加実装は不要。

fast-domain がこの提案を反映した後、repom 側では必要に応じてこの proposal を削除する。

---

## 関連ファイル・資料

fast-domain 側で確認した主な対象:

- `C:\Users\jj\Desktop\workspace_main\projects\fast-domain\pyproject.toml`
- `C:\Users\jj\Desktop\workspace_main\projects\fast-domain\uv.lock`
- `C:\Users\jj\Desktop\workspace_main\projects\fast-domain\src\fast_domain\routes.py`
- `C:\Users\jj\Desktop\workspace_main\projects\fast-domain\src\fast_domain\invoke\config.py`
- `C:\Users\jj\Desktop\workspace_main\projects\fast-domain\src\fast_domain\invoke\loader.py`
- `C:\Users\jj\Desktop\workspace_main\projects\fast-domain\src\fast_domain\config.py`
- `C:\Users\jj\Desktop\workspace_main\projects\fast-domain\src\fast_domain\assets\config.py`
- `C:\Users\jj\Desktop\workspace_main\projects\fast-domain\tests\unit_tests\test_model_auto_import.py`
- `C:\Users\jj\Desktop\workspace_main\projects\fast-domain\docs\issues\active\149_extract_shared_infra_to_standalone_package.md`

repom / basekit 側の基準 commit:

- repom: `70f3198 refactor: move shared utilities to basekit`
- basekit: `ccdf6f3fbcfee5e0b93b27e294ea6507af408dc2`

---

## 検証候補

fast-domain 側の変更後、少なくとも次を確認する。

```bash
uv run pytest tests/unit_tests/test_model_auto_import.py
uv run pytest tests/unit_tests/test_routes.py
uv run pytest tests/unit_tests/arq/test_bootstrap.py tests/unit_tests/db/test_db_bootstrap.py tests/unit_tests/test_arq_redis_startup.py
uv run ruff check src tests
```

余裕があれば full test を実行する。

```bash
uv run pytest
```

---

## ディスカッションログ

### 2026-05-19 - repom

- repom issue 066 の完了後、fast-domain 側の影響を調査。
- fast-domain には `repom._.discovery` 直接 import が残っていることを確認。
- Docker 管理クラスへの直接依存は見つからず、`repom.postgres.manage` / `repom.redis.manage` 経由の利用で問題ないと判断。

---

## 結果

未定。
