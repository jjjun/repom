# Issue #9: テストインフラストラクチャの改善

**ステータス**: 🟢 進行中

**作成日**: 2025-11-16

**優先度**: 高

**関連Issue**: mine-py からの要望（repom-testing-support.md）

---

## 問題の説明

### repom 自体のテスト問題

1. **クリーンアップ不十分**
   - 現在の `db_test_fixtures.py` は `db_create()` → `db_delete()` を毎テストで実行
   - セッション内のキャッシュやトランザクション状態が残る可能性
   - テスト実行時に「データベースのクリーンアップが不十分」と感じることがある

2. **パフォーマンス問題**
   - 毎テスト関数でDB再作成（`db_create()` + `db_delete()`）
   - テスト数が増えると実行時間が長くなる

3. **トランザクション分離がない**
   - 1つのDBセッションを共有
   - 複数テスト間でデータ干渉の可能性
   - テストの独立性が保証されない

### mine-py での問題（外部プロジェクトの例）

4. **インデックス重複エラー**
   ```
   sqlite3.OperationalError: index ix_time_blocks_date already exists
   ```
   - `Base.metadata.drop_all()` + `create_all()` を使用
   - Alembic で作成したインデックスが残留
   - 54件のテスト全てが失敗

5. **環境混在の問題**
   - アプリケーション用の `engine` をテストでも使用
   - テスト専用のデータベース管理が困難

---

## 提案される解決策

### 📋 採用方針（確定）

#### 1. **トランザクションロールバック方式**（案A採用）

**理由**:
- ⚡ **超高速**: DB再作成不要、ロールバックのみ
- ✅ **完全な分離**: 各テストが独立したトランザクション内
- ✅ **クリーンな状態**: ロールバックで確実にリセット

**実装方針**:
```python
@pytest.fixture(scope='session')
def db_engine():
    """セッション全体で1つのエンジンを共有"""
    engine = create_engine(config.db_url)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()

@pytest.fixture()
def db_test(db_engine):
    """各テストで独立したトランザクション"""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = scoped_session(sessionmaker(bind=connection))
    
    yield session
    
    session.close()
    transaction.rollback()  # 自動ロールバック
    connection.close()
```

#### 2. **repom/testing.py の追加**（アプローチ1採用）

**理由**:
- repom は最小限の機能を提供する哲学
- シンプルなヘルパー関数のみ
- 各プロジェクトが必要に応じて拡張可能

**提供する機能**:
- トランザクションロールバック方式のフィクスチャヘルパー
- カスタムDB URL対応
- 外部プロジェクトが簡単に使える設計

**却下した案**:
- ❌ `TestDatabaseManager` クラス（mine-py提案）
  - 理由: repom の哲学に合わない（最小限主義）
  - 過剰な機能（各プロジェクトで実装すべき）

#### 3. **Alembic テーブルの扱い**

**方針**: テストでは Alembic を使わない

**理由**:
- ✅ テストは `Base.metadata.create_all()` でスキーマ作成
- ✅ マイグレーション履歴は不要（テストは常にクリーンな状態から開始）
- ✅ `alembic_version` テーブルが存在しても無害（単に無視される）
- ❌ Alembic マイグレーションをテストで使うのはナンセンス

**Alembic テーブルとは**:
```sql
-- Alembic が自動作成するマイグレーション履歴テーブル
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL PRIMARY KEY
);
```

**mine-py のエラー原因**:
- Alembic で作成したインデックスが `Base.metadata` に含まれていない
- `drop_all()` がインデックスを削除できない
- `create_all()` が再作成を試みて重複エラー

**解決策**:
- テスト専用のエンジン/DB URLを使用
- Alembic とテストを完全分離

---

## 影響範囲

### repom 内部
- ✏️ `tests/db_test_fixtures.py`: 完全書き換え
- ➕ `repom/testing.py`: 新規追加
- ✏️ `tests/conftest.py`: 必要に応じて調整
- 📖 `README.md`: テスト戦略セクション追加
- 📖 `docs/guides/testing_guide.md`: 新規ガイド作成

### 外部プロジェクト（mine-py など）
- 📖 `repom/testing.py` のヘルパーを使用可能
- 📖 ベストプラクティスドキュメントを参照
- ⚠️ 既存テストコードの修正が必要な場合あり

---

## 実装計画

### Phase 1: repom テストフィクスチャの改善 ✅
- [x] `tests/db_test_fixtures.py` をトランザクションロールバック方式に書き換え
- [x] `db_engine` フィクスチャ追加（session スコープ）
- [x] `db_test` フィクスチャ改善（トランザクション分離）

### Phase 2: repom/testing.py の実装
- [ ] `repom/testing.py` 新規作成
- [ ] `create_test_db_fixture()` ヘルパー関数実装
- [ ] カスタムDB URL対応
- [ ] ドキュメント文字列の充実

### Phase 3: テストの実行と検証
- [ ] repom の全テスト実行（186テスト）
- [ ] パフォーマンス測定（実行時間比較）
- [ ] テスト分離の確認（データ干渉がないか）

### Phase 4: ドキュメント整備
- [ ] `README.md` にテスト戦略セクション追加
- [ ] `docs/guides/testing_guide.md` 作成
  - テスト戦略の説明
  - ベストプラクティス
  - 外部プロジェクト向けガイド
  - mine-py での使用例
- [ ] `.github/copilot-instructions.md` 更新

### Phase 5: mine-py への展開（オプション）
- [ ] mine-py のテストコード修正提案
- [ ] `repom/testing.py` の使用例提供
- [ ] 54件のテスト修正サポート

---

## テスト計画

### repom 自体のテスト
1. **機能テスト**
   - 全186テストが成功すること
   - トランザクション分離が機能すること
   - セッション間でデータ干渉がないこと

2. **パフォーマンステスト**
   - 旧方式と新方式の実行時間比較
   - 目標: 50%以上の高速化

3. **エッジケーステスト**
   - 複数テストファイル同時実行
   - テスト失敗時のロールバック
   - セッションスコープフィクスチャの動作

### repom/testing.py のテスト
1. **ユニットテスト**
   - ヘルパー関数の基本動作
   - カスタムDB URL対応
   - エラーハンドリング

2. **統合テスト**
   - 実際のテストシナリオでの使用
   - 外部プロジェクトでの動作確認

---

## 技術的決定事項

### 1. トランザクションロールバック方式の詳細

**セッションスコープ（`db_engine`）**:
- テストセッション全体で1回だけDB作成
- 全テスト終了後にクリーンアップ
- エンジンとコネクションプールを共有

**ファンクションスコープ（`db_test`）**:
- 各テスト関数で独立したトランザクション
- テスト終了時に自動ロールバック
- 他のテストに影響を与えない

**メリット**:
- DB再作成のオーバーヘッドが1回だけ
- トランザクション分離により完全な独立性
- ロールバックで確実なクリーンアップ

**デメリット**:
- DDL変更（テーブル作成/削除）はトランザクション内で不可
  - → repom では問題なし（スキーマは固定）

### 2. repom/testing.py の設計

**方針**: シンプルなヘルパー関数のみ

```python
# repom/testing.py
def create_test_db_fixture(db_url: str = None):
    """
    トランザクションロールバック方式のテストフィクスチャを作成
    
    Args:
        db_url: テスト用データベースURL（省略時は config.db_url）
    
    Returns:
        tuple: (db_engine_fixture, db_test_fixture)
    
    Example:
        # 外部プロジェクトでの使用例
        from repom.testing import create_test_db_fixture
        
        db_engine, db_test = create_test_db_fixture()
    """
```

**理由**:
- repom の哲学（最小限主義）に合致
- 外部プロジェクトが自由に拡張可能
- メンテナンスコストが低い

### 3. Alembic との関係

**テストの哲学**:
```
テストは常にクリーンな状態から開始する
→ マイグレーション履歴は不要
→ Base.metadata.create_all() を使用
```

**Alembic の役割**:
```
本番環境でのスキーマ変更管理
→ マイグレーションファイルで履歴管理
→ テストとは無関係
```

**ベストプラクティス**:
- ✅ テスト: `Base.metadata.create_all()`
- ✅ 本番: `alembic upgrade head`
- ❌ テストで Alembic を使うのは避ける

---

## 関連リソース

### repom 内部
- `tests/db_test_fixtures.py`: 既存フィクスチャ
- `tests/conftest.py`: pytest設定
- `repom/db.py`: データベース接続
- `repom/config.py`: 環境別設定

### 外部ドキュメント
- [pytest fixtures documentation](https://docs.pytest.org/en/stable/fixture.html)
- [SQLAlchemy Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)
- [Transaction Rollback Pattern](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)

### 参考Issue
- mine-py: `repom-testing-support.md`
- Issue #6: SQLAlchemy 2.0 スタイルへの移行

---

## 議論ログ

### 2025-11-16: 初期相談

**ユーザー質問**:
1. db_test_fixtures.py と conftest.py の役割分担は明確か？
   - **回答**: 明確。conftest.py は環境変数、db_test_fixtures.py はDBフィクスチャ
   - **問題**: フィクスチャのスコープに改善の余地あり

2. repom/testing.py の機能範囲は？
   - **決定**: アプローチ1（シンプルなヘルパー関数のみ）採用
   - **理由**: repom の最小限主義に合致

3. Alembic テーブル残留について
   - **方針**: テストでは Alembic を使わない
   - **理由**: テストは常にクリーンな状態から、マイグレーション履歴は不要

### 2025-11-16: Alembic テーブルの詳細議論

**ユーザー質問**: 何故、テストDBで Alembic テーブルが存在するのか？

**回答**:
- repom の `db_create()` は `Base.metadata.create_all()` のみ
- Alembic テーブルは作成しない（正しい実装）
- mine-py の問題は「Alembic テーブル」ではなく「Alembic で作成したインデックス」

**根本原因（mine-py）**:
1. アプリケーション用の `engine` をテストでも使用
2. 開発DBで Alembic 実行 → インデックス作成
3. テストで同じDBを使用 → インデックスが残留
4. `drop_all()` がインデックスを削除できない（メタデータに含まれていない）
5. `create_all()` が再作成を試みて失敗

**解決策**:
- テスト専用のDB URLを使用（環境分離）
- または `repom/testing.py` のヘルパーを使用

---

## 進捗状況

### 2025-11-16
- ✅ 問題分析と方針決定
- ✅ Phase 1: `tests/db_test_fixtures.py` 改善完了
- 🚧 Phase 2: `repom/testing.py` 実装中

### 次のステップ
1. `repom/testing.py` の実装
2. テスト実行と検証
3. ドキュメント整備

---

最終更新: 2025-11-16
