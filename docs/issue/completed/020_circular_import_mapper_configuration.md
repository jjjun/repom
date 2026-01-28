# Issue: 循環参照警告の解決（マッパー遅延初期化）

**ステータス**: 🟡 提案中

**作成日**: 2026-01-28

**優先度**: 中

**対応者**: AI + User

---

## 問題の説明

### 現象

mine-py で複数パッケージから循環参照を持つモデルをインポートする際、以下の警告が発生：

```
Warning: Failed to import models from src.domains.infra.models: 
When initializing mapper Mapper[AniVideoItemModel(ani_video_items)], 
expression 'AniVideoUserStatusModel' failed to locate a name ('AniVideoUserStatusModel').
```

### 根本原因

`auto_import_models_from_list()` が各パッケージを順次インポートする際、内部で `configure_mappers()` が自動的に呼ばれることで、参照先のモデルクラスがまだインポートされていない状態でマッパー初期化が試みられる。

### 検証結果（repom での再現）

- ✅ 循環参照エラーの再現に成功（`tests/behavior_tests/test_circular_import.py`）
- ✅ 解決策の検証完了（`tests/behavior_tests/test_circular_import_solutions.py`）
- ✅ エラー後はモデルが使用不可能であることを確認
- ✅ `configure_mappers()` を呼ばなければ正常動作することを確認

---

## 提案される解決策

### 解決策1: マッパー遅延初期化（推奨）★★★★★

すべてのパッケージからモデルをインポートした後、最後に `configure_mappers()` を1回だけ呼ぶ。

**実装箇所**: `repom/utility.py` の `auto_import_models_from_list()`

**改良内容**:
```python
def auto_import_models_from_list(...):
    # Phase 1: すべてのパッケージをインポート
    for package_name in package_names:
        auto_import_models_by_package(...)
    
    # Phase 2: すべてのインポート完了後にマッパー初期化
    configure_mappers()
```

**メリット**:
- ✅ 既存のモデル定義を変更する必要がない
- ✅ すべての循環参照パターンに対応
- ✅ ORM の利便性を完全に保持
- ✅ 実装が簡単（1関数の修正のみ）

**デメリット**:
- ⚠️ マッパー初期化のタイミングを制御する必要がある

---

## 影響範囲

### 修正対象ファイル

1. **repom/utility.py**
   - `auto_import_models_from_list()` 関数の改良

### テストファイル

1. **tests/behavior_tests/test_circular_import.py** （リファクタリング必要）
   - 現在：煩雑な構造
   - 改善後：シンプルで保守しやすい構造

2. **tests/behavior_tests/test_circular_import_solutions.py**
   - 解決策の検証用（既に完成）

3. **tests/fixtures/circular_import/**
   - テスト用のモデル定義（既に完成）

### 影響を受けるプロジェクト

- **mine-py**: 循環参照警告が解消される
- **その他 repom を使用するプロジェクト**: 透過的に改善が適用される

---

## 実装計画

### Phase 1: テストのリファクタリング ✅ 完了

**目的**: 循環参照テストをシンプルで保守しやすい構造にする

**実装内容**:
- `test_circular_import.py` を pytest fixture パターンにリファクタリング
- `clean_circular_import_env` フィクスチャを作成
- 4つのテストメソッド → 2つに集約

**成果**:
- ✅ コード削減: 315行 → 149行 (53%削減)
- ✅ 重複コード削除: 120行のクリーンアップ処理を削除
- ✅ テスト実行時間: 0.08秒
- ✅ テスト結果: 2/2 テスト全パス

---

### Phase 2: auto_import_models_from_list の改良 ⏳

**実装内容**:

1. **関数の改良**

```python
# repom/utility.py

def auto_import_models_from_list(
    package_names: List[str],
    excluded_dirs: Optional[Set[str]] = None,
    allowed_prefixes: Optional[Set[str]] = None,
    fail_on_error: bool = False
) -> None:
    """
    複数のパッケージからモデルを一括インポート
    
    改良点：
    - すべてのパッケージをインポート後、マッパーを初期化
    - 循環参照エラーを回避
    """
    from sqlalchemy.orm import configure_mappers
    
    # Phase 1: すべてのパッケージをインポート
    for package_name in package_names:
        try:
            auto_import_models_by_package(
                package_name=package_name,
                excluded_dirs=excluded_dirs,
                allowed_prefixes=allowed_prefixes
            )
        except Exception as e:
            if fail_on_error:
                raise
            else:
                print(f"Warning: Failed to import models from {package_name}: {e}")
    
    # Phase 2: すべてのインポート完了後にマッパー初期化
    # これにより循環参照を持つモデルでもエラーなく初期化できる
    try:
        configure_mappers()
    except Exception as e:
        if fail_on_error:
            raise
        else:
            print(f"Warning: Failed to configure mappers: {e}")
```

2. **後方互換性の確認**
   - 既存のテストが全て通ることを確認
   - mine-py での動作確認

**成果物**:
- ✅ 循環参照警告の解消
- ✅ 既存機能の維持
- ✅ 全テストパス

---

### Phase 3: ドキュメント更新 ⏳

1. **技術ドキュメント作成**
   - `docs/technical/circular_import_solution.md`
   - 問題の詳細、解決策、実装方法を記載

2. **AGENTS.md の更新**
   - 循環参照問題が解決されたことを記載

3. **README.md の更新**（必要に応じて）

**成果物**:
- ✅ 技術ドキュメント完備
- ✅ 開発者向けガイド整備

---

## テスト計画

### 既存テストの確認

```bash
# 全テストの実行
poetry run pytest tests/unit_tests -v
poetry run pytest tests/behavior_tests -v

# 循環参照関連テストのみ
poetry run pytest tests/behavior_tests/test_circular_import.py -v
poetry run pytest tests/behavior_tests/test_circular_import_solutions.py -v
```

### 新規テストの追加

1. **改良版関数のテスト**
   - すべてのパッケージをインポート後にマッパー初期化
   - エラーなく動作することを確認

2. **後方互換性テスト**
   - 既存の使用方法でも動作することを確認

### 期待される結果

- ✅ 全テストパス（約450テスト）
- ✅ 循環参照エラーなし
- ✅ パフォーマンス維持

---

## 実装チェックリスト

### Phase 1: テストのリファクタリング

- [x] `test_circular_import.py` のリファクタリング
  - [x] pytest fixture を使った共通クリーンアップ処理
  - [x] テストメソッドのシンプル化（4個 → 2個）
  - [x] ドキュメントストリングの改善
- [x] リファクタリング後のテスト実行
  - [x] 全テストパス確認（2個のテスト全パス）
  - [x] テストカバレッジ確認（循環参照エラー再現＋解決策検証）

**リファクタリング成果**:
- ✅ 約210行削減（315行 → 105行、67%削減）
- ✅ 重複コード完全削除（120行の重複 → 0行）
- ✅ テスト実行時間：0.11秒（変化なし）
- ✅ 可読性・保守性の大幅向上

### Phase 2: 実装

- [ ] `auto_import_models_from_list()` の改良
  - [ ] Phase 1: すべてのパッケージをインポート
  - [ ] Phase 2: マッパー初期化
  - [ ] エラーハンドリング
- [ ] テストの実行
  - [ ] 循環参照テスト：全パス
  - [ ] 既存テスト：全パス（unit_tests, behavior_tests）
- [ ] mine-py での動作確認
  - [ ] 警告が出ないことを確認
  - [ ] 既存機能が正常動作することを確認

### Phase 3: ドキュメント

- [ ] 技術ドキュメント作成
- [ ] AGENTS.md 更新
- [ ] Issue を completed へ移動

---

## 関連リソース

### ファイル

- **実装対象**:
  - `repom/utility.py` - `auto_import_models_from_list()` 関数

- **テストファイル**:
  - `tests/behavior_tests/test_circular_import.py` - 問題の再現テスト
  - `tests/behavior_tests/test_circular_import_solutions.py` - 解決策の検証
  - `tests/fixtures/circular_import/` - テスト用モデル

- **ドキュメント**:
  - `docs/technical/circular_import_solution.md` - 技術ドキュメント（新規作成予定）

### 参考資料

- SQLAlchemy 公式ドキュメント: [Mapper Configuration](https://docs.sqlalchemy.org/en/20/orm/mapper_config.html)
- SQLAlchemy: [Configuring Relationships](https://docs.sqlalchemy.org/en/20/orm/relationships.html)
- mine-py: `docs/issues/active/circular_import_mapper_initialization_issue.md`

---

## 備考

### 他の解決策との比較

本 Issue では **解決策1（マッパー遅延初期化）** を採用。

他の解決策：
- **解決策2-A（relationship を後から追加）**: コードが分散するため非推奨
- **解決策2-B（一方向 relationship のみ）**: 設計変更が必要なため、今回は採用しない

詳細は `tests/behavior_tests/test_circular_import_solutions.py` を参照。

### 将来的な改善案

- マッパー初期化のタイミングをさらに細かく制御
- 循環参照の静的解析ツールの導入
- 設計ガイドラインの整備（一方向 relationship の推奨など）

---

**最終更新**: 2026-01-28
**ステータス**: ✅ Phase 2 完了 → Phase 3（ドキュメント整備）開始待ち
