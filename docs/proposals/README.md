# Proposals

このディレクトリは、`repom` から他プロジェクト・他パッケージへ送る提案書を置く場所です。

`docs/ideas/` は repom 自体の機能アイデア、`docs/issue/` は repom 内の実装タスクを扱います。
一方、`docs/proposals/` は repom 側だけでは完結できず、外部システム側の変更や判断が必要なときだけ使います。

提案書は一時ファイルとして管理します。提案先で対応が完了したら削除してください。

## 対象ファイル

```text
docs/proposals/
├── README.md
├── _template.md
└── NNN_<target>_<slug>.md
```

- proposal 本体は `docs/proposals/` 直下に置きます
- `README.md` と `_template.md` は採番対象に含めません

## 命名ルール

```text
NNN_<target>_<slug>.md
```

- `NNN`: 3 桁の連番です。`001`, `002`, `003` のようにゼロ埋めします
- `<target>`: 提案先プロジェクト・パッケージを表す snake_case 名です。例: `mine_py`, `fast_domain`, `mine_js_monorepo`, `py_cr_wrapper`
- `<slug>`: 提案内容を短く表す snake_case です。例: `align_session_api`, `router_prefix_option`

例:

- `001_mine_py_migrate_to_public_transaction_api.md`
- `002_fast_domain_router_prefix_option.md`

## 採番ルール

新しい proposal を作るときは、`docs/proposals/` 直下の `.md` を確認し、`README.md` と `_template.md` を除いた既存 proposal の番号から次の値を採番します。

- 既存 proposal がなければ `001` から開始します
- 既存 proposal があれば、最大番号に `1` を足した値を使います
- 欠番があっても埋めず、必ず最大番号 `+1` を使います
- 既存ファイルのリネームによる採番し直しはしません

## AI エージェント向け手順

1. `docs/proposals/` 直下の proposal ファイル名を確認する
2. `README.md` と `_template.md` を除いた `.md` から最大の `NNN` を読む
3. `NNN + 1` を 3 桁ゼロ埋めして新規ファイル名を決める
4. `_template.md` をコピーして新規 proposal を作成する
5. テンプレートを埋め、repom 側だけでは完結できない変更点を整理する
6. repom 側で対処できる範囲があれば、proposal だけで終わらせず併せて実装する

## 補足

- 提案書は repom 外の変更や意思決定が必要な場合にだけ作成します
- repom 内で実装できる機能追加・修正は `docs/issue/` または `docs/ideas/` を使います
- 提案先で対応が完了したら、関連する repom 側変更を確認したうえで proposal ファイルを削除します
