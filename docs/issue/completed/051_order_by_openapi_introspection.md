# Issue #051: `order_by` OpenAPI introspection と FastAPI helper の追加

**ステータス**: ✅ 完了

**作成日**: 2026-03-16

**完了日**: 2026-03-17

**優先度**: 中

## 概要

fast-domain から、Repository に定義済みの `allowed_order_columns` / `default_order_by` を OpenAPI に反映したい、という提案 (`repom_order_by_openapi_proposal.md`) を受領した。

調査の結果、問題提起自体は妥当だが、`repom` にとっては「FastAPI dependency を直接返す helper を追加する」だけでは責務の切り方が少し狭い。`repom` 側ではまず framework-agnostic な `order_by` introspection API を正本として持ち、その上に FastAPI/OpenAPI 向け helper を薄く載せる構成が適している。

また、`repom` はまだ未公開パッケージであるため、このタイミングでは後方互換維持よりも将来負債の削減を優先する。既存仕様のうち HTTP/OpenAPI 仕様として曖昧さを残す部分は、この Issue で整理してよい。

## 調査結果

### 1. 現状の `repom` 実装

`repom` にはすでに `order_by` の実行時仕様が存在する。

- `QueryBuilderMixin.allowed_order_columns`
- `QueryBuilderMixin.default_order_by`
- `parse_order_by()`
- `set_find_option()`

現在の仕様の要点:

- `parse_order_by()` は `column:asc|desc` を受け付ける
- `column` 単独指定も許可し、`asc` として解釈する
- ホワイトリスト外カラムは拒否する
- モデルに実在しないカラムも拒否する
- `default_order_by` は文字列だけでなく SQLAlchemy 式も許容する
- `order_by` 未指定時は `default_order_by`、それも無ければ `model.id.asc()` にフォールバックする

つまり、HTTP 層へ公開すべき `order_by` 候補の正本はすでに `repom` にある。

### 2. 現状の FastAPI 統合

`repom` には `FilterParams.as_query_depends()` があり、Pydantic/Query シグネチャを動的生成する前例がある。一方で `order_by` については同等の helper はまだ無い。

### 3. 現状の fast-domain 実装

fast-domain 側では `src/fast_domain/dependencies.py` の `order_by_params()` が単純な `str = Query(None)` を返しており、OpenAPI 上は `string` としてしか公開されない。

また `src/fast_domain/endpoints/list.py` では、endpoint decorator 側で `default_order_by` を `order_params["order_by"]` へ後付けしている。これは `repom` の `default_order_by` と責務が一部重複している。

### 4. 提案書から見直すべき点

提案書は `build_order_by_query_depends(repository_class)` を主 API にしているが、`repom` 側の第一責務は FastAPI 専用 helper ではなく、Repository 定義から公開可能な `order_by` 仕様を導出することにある。

この introspection がないまま helper だけ実装すると:

- 将来 FastAPI 以外で再利用しにくい
- テストが HTTP 層に寄りすぎる
- fast-domain 側が別用途で候補一覧だけ欲しい場合に再分解が必要

## 問題

現状では、`repom` にある `order_by` 実行時仕様と、OpenAPI に露出する HTTP 仕様が分離している。

その結果:

- OpenAPI からソート可能な候補が分からない
- fast-domain 側で `order_by` の説明責務を持つことになり、仕様の二重管理が起こる
- `allowed_order_columns` と実在カラムの不一致を HTTP 層ごとに解決する必要がある

## 設計方針

`repom` では責務を 2 層に分ける。

1. Repository クラスから公開可能な `order_by` 値を導出する introspection API
2. その introspection 結果を使って FastAPI Query dependency を構築する helper

### A. Introspection API を正本にする

最低限、以下の情報を Repository クラスから導出できるようにする。

- 対象モデル
- OpenAPI に公開可能なソートカラム一覧
- OpenAPI に公開する canonical な `order_by` 値一覧
- OpenAPI に反映可能な default 値

想定 API:

```python
get_order_by_columns(repository_class) -> list[str]
get_order_by_values(repository_class, include_implicit_asc: bool = False) -> list[str]
get_order_by_default_value(repository_class) -> str | None
```

補足:

- 引数は repository instance ではなく repository class を受ける
- session を必要とせず動作させる
- `BaseRepository` / `AsyncBaseRepository` の両方を対象にする

### B. FastAPI helper は薄いラッパーにする

OpenAPI enum 化は上記 introspection を利用する薄い helper として提供する。

想定 API:

```python
build_order_by_query_depends(
    repository_class,
    *,
    include_implicit_asc: bool = False,
    description: str | None = None,
) -> Callable
```

返却値は既存の fast-domain 実装に合わせ、以下の形を維持する。

```python
{"order_by": "created_at:desc"}
```

### C. 候補生成ルール

OpenAPI に公開するカラムは、以下の積集合とする。

- `repository_class.allowed_order_columns`
- 対象モデルに実在する属性

公開値の canonical form は以下を基本とする。

- `{column}:asc`
- `{column}:desc`

`column` 単独指定はサポートしない。runtime 仕様・OpenAPI 仕様の両方を canonical form に統一する。

### D. default の公開ルール

`default_order_by` の扱いは次のように分ける。

- 文字列 `created_at:desc` の場合: Query default として公開可能
- 文字列 `created_at` の場合: 不正な設定として扱う
- SQLAlchemy 式の場合: OpenAPI default には反映しない

これにより、OpenAPI へ出せる範囲だけを明確に仕様化できる。

### E. FastAPI 依存は遅延 import にする

`repom` 本体の Poetry 依存には `fastapi` が本番依存として入っていないため、`FilterParams.as_query_depends()` と同様に helper 内で遅延 import する。

必要に応じて以下のどちらかを選ぶ。

- 現状どおり lazy import + ImportError メッセージ整備
- 将来的に FastAPI extra を用意する

本 Issue では前者を優先する。

## 仕様整理方針

`repom` は未公開であり、利用者も実質的に fast-domain 系に限定されるため、本 Issue では後方互換性を最優先しない。

この Issue で優先すること:

- `order_by` の HTTP 向け仕様を canonical form に寄せる
- FastAPI/OpenAPI に露出する仕様と runtime 仕様のズレを減らす
- repository 側の責務と endpoint/decorator 側の責務を整理しやすい土台を作る

この方針に基づき、以下の破壊的整理を許容する。

- OpenAPI helper が公開する候補を canonical form (`{column}:asc|desc`) に限定する
- bare column を廃止し、canonical form のみ受け付ける
- `default_order_by` の公開可能範囲を文字列ベースの canonical 値に寄せる

`parse_order_by()` の bare column 許容は HTTP 仕様として曖昧さの原因になるため、本 Issue では廃止する。曖昧な入力形式を早期に排除した方が、将来の利用者に一貫した仕様を提示しやすい。

一方で、fast-domain 側の移行コストを下げるため、破壊的変更に対応する移行資料は `repom` 側に残す。

## fast-domain 側の追従方針

`repom` 実装後、fast-domain 側は以下の順で移行する。

1. `order_by_params` を Repository 非依存 fallback として残す
2. Repository が明確な endpoint では `Depends(build_order_by_query_depends(RepoClass))` へ切り替える
3. decorator で注入している `default_order_by` と repository 定義の責務分担を整理する

特に `list_endpoint(..., default_order_by=...)` は、repository 側 `default_order_by` と二重管理になりやすいため、今後はどちらを正本にするか fast-domain 側で別途整理が必要である。ただし本 Issue では `repom` 側の introspection/helper 提供までをスコープとする。

`repom` 側では fast-domain 向けに最低限以下を残す。

- 旧仕様から新仕様への移行ポイント
- bare column 廃止時の修正例
- `order_by_params` から `build_order_by_query_depends()` への置換例
- decorator 側 `default_order_by` と repository 側 `default_order_by` の整理指針

## 影響範囲

- `repom/repositories/_core.py`
- `repom/repositories/_query_builder.py`
- `repom/repositories/__init__.py`
- `repom/__init__.py`
- 新規 helper モジュール追加の可能性
- `tests/unit_tests/` の repository / FastAPI 関連テスト
- `docs/guides/` または `docs/technical/` の移行資料
- 必要に応じて README / guides

## 実装計画

1. Repository class から model を安全に解決する内部 utility を定義する
2. `allowed_order_columns` とモデル属性の積集合を返す introspection API を実装する
3. `order_by` 入力仕様を canonical form 基準で見直し、必要なら bare column を廃止する
4. canonical な `order_by` 値一覧を返す API を実装する
5. `default_order_by` を OpenAPI 用に正規化する API を実装する
6. FastAPI Query dependency helper を追加する
7. package export を整理する
8. fast-domain 向け移行資料と利用例を追加する

## テスト計画

### Unit tests

- `allowed_order_columns` と実在カラムの積集合だけが返る
- 存在しないカラムが enum 候補に出ない
- sync / async repository class の両方で動作する
- `default_order_by='created_at:desc'` が OpenAPI default に反映される
- bare column の `default_order_by='created_at'` は不正設定としてエラーになる
- `default_order_by` が SQLAlchemy 式のとき OpenAPI default を出さない
- `parse_order_by("created_at")` がエラーになる

### FastAPI integration tests

- OpenAPI schema に `order_by` enum が出る
- enum 候補が repository 定義と一致する
- dependency の返却値が `{"order_by": ...}` である
- helper 未使用時の既存 repository 動作に影響しない

## 完了条件

- [x] Repository class ベースの `order_by` introspection API が追加されている
- [x] FastAPI Query helper が追加されている
- [x] `order_by` の canonical runtime 仕様が定義され、必要なら破壊的整理が実施されている
- [x] sync / async 両系統のテストが追加されている
- [x] OpenAPI enum 表示の統合テストが追加されている
- [x] fast-domain 向け移行資料が追加されている
- [x] 利用ガイドまたは README が更新されている

## 実装サマリ

- `repom/repositories/_order_by.py` を新規作成し、`get_order_by_columns()` / `get_order_by_values()` / `get_order_by_default_value()` / `build_order_by_query_depends()` / `VirtualColumnError` を実装
- `parse_order_by()` を canonical form 必須に統一（bare column 廃止）
- `virtual_order_columns` サポートを Issue #052 として追加実装
- `repom/__init__.py` / `repom/repositories/__init__.py` から公開 export
- `tests/unit_tests/test_order_by_openapi.py` に 16 件のテストを追加（全パス）
- `docs/guides/repository/order_by_guide.md` に利用ガイドと移行メモを追加
- `include_implicit_asc` オプションは canonical 統一方針と逆方向のため導入せず

## 関連リソース

- 提案書: `C:/Users/jj/Desktop/workspace_main/projects/fast-domain/docs/tmp/repom_order_by_openapi_proposal.md`
- 現行実装: `repom/repositories/_core.py`
- 現行実装: `repom/repositories/_query_builder.py`
- 既存 FastAPI precedent: `FilterParams.as_query_depends()`
- fast-domain 現行 dependency: `C:/Users/jj/Desktop/workspace_main/projects/fast-domain/src/fast_domain/dependencies.py`
- fast-domain 現行 list decorator: `C:/Users/jj/Desktop/workspace_main/projects/fast-domain/src/fast_domain/endpoints/list.py`
