# スキーマ検証コマンド

## ステータス
- **段階**: アイディア
- **優先度**: 中
- **複雑度**: 低
- **作成日**: 2025-11-14
- **最終更新**: 2025-11-14

## 概要

ビルド/デプロイ時にすべてのモデルスキーマを検証する CLI コマンドを作成し、本番環境に到達する前にスキーマ生成エラーを検出します。

## モチベーション

現在、スキーマ生成エラーは実行時に `get_response_schema()` が呼び出されたときにのみ発生します。これは以下を意味します:
- エラーが本番環境まで発見されない可能性がある
- CI/CD パイプラインがスキーマの問題を早期に検出できない
- 開発者はすべてのレスポンスエンドポイントを手動でテストする必要がある

検証コマンドにより以下が可能になります:
- **CI/CD 統合**: 自動テストの一部として実行
- **デプロイ前の検証**: リリース前に問題を検出
- **開発ワークフロー**: 開発中の迅速な検証

## ユースケース

### 1. CI/CD パイプライン
```yaml
# .github/workflows/test.yml
- name: Validate Model Schemas
  run: poetry run repom validate-schemas
```

### 2. プレコミットフック
```bash
# .git/hooks/pre-commit
poetry run repom validate-schemas || exit 1
```

### 3. 開発ワークフロー
```bash
# 開発中の迅速な検証
poetry run repom validate-schemas
# ✓ すべてのスキーマが正常に検証されました（15モデル）
```

## 検討可能なアプローチ

### アプローチ 1: スキャンと検証
**説明**: すべての BaseModel サブクラスを自動検出し、`get_response_schema()` を呼び出す

**長所**:
- 包括的な検証
- 手動設定不要
- すべてのスキーマエラーを検出

**短所**:
- レスポンス用でないモデルも検出する可能性
- モデルインポートが必要（副作用？）

**例**:
```python
# repom/scripts/validate_schemas.py
def validate_all_schemas():
    models = discover_base_models()  # すべての BaseModel サブクラスをスキャン
    for model_cls in models:
        try:
            model_cls.get_response_schema()
            print(f"✓ {model_cls.__name__}")
        except SchemaGenerationError as e:
            print(f"✗ {model_cls.__name__}: {e}")
            return False
    return True
```

### アプローチ 2: 明示的な登録
**説明**: 検証するモデルを登録することを要求

**長所**:
- 検証対象の明示的な制御
- 予期しない副作用なし
- 意図が明確

**短所**:
- 手動登録が必要
- モデルを見逃す可能性

**例**:
```python
# モデルファイル内
@register_for_validation
class MyModel(BaseModel):
    pass
```

### アプローチ 3: 設定ファイル
**説明**: 設定ファイルに検証するモデルをリストアップ

**長所**:
- 集中管理された設定
- モデルの包含/除外が容易
- コード変更不要

**短所**:
- 保守する追加設定
- 古くなる可能性

**例**:
```yaml
# repom.validation.yml
models:
  - repom.models.sample.Sample
  - repom.models.user_session.UserSession
```

## 技術的考慮事項

### 実装
- 既存の `get_response_schema()` メソッドを使用
- Phase 2 エラーハンドリング（dev 環境の動作）を活用
- 最初のエラーだけでなく、すべてのエラーを報告
- サマリー統計を提供

### パフォーマンス
- 大きなモデルではスキーマ生成が遅い可能性
- 複数モデルの並列検証を検討
- 可能であれば結果をキャッシュ

### 依存関係
- 新しい依存関係不要
- 既存の repom インフラを使用
- Poetry スクリプトと互換性あり

### 出力フォーマット
- 色付きコンソール出力（✓/✗）
- CI/CD パース用の JSON フォーマットオプション
- 終了コード: 0（成功）または 1（失敗）

## 統合ポイント

### 影響を受けるコンポーネント
- `repom/scripts/` - 新規スクリプト: `validate_schemas.py`
- `pyproject.toml` - Poetry スクリプトエントリーポイントを追加
- `README.md` - 新しいコマンドをドキュメント化

### 既存機能との相互作用
- `BaseModel.get_response_schema()` を使用
- Phase 2 エラー検出を活用
- EXEC_ENV 環境変数と互換性あり

### 出力例
```
$ poetry run repom validate-schemas

モデルスキーマを検証中...

✓ Sample (repom.models.sample)
✗ UserSession (repom.models.user_session)
  エラー: 型 'SessionData' が定義されていません
  提案: 'from typing import ForwardRef' を追加して型を定義してください
  
✓ Product (myapp.models.product)
✗ Order (myapp.models.order)
  エラー: 型 'OrderItem' が定義されていません
  提案: OrderItem をインポートするか、文字列リテラル 'OrderItem' を使用してください

サマリー: 2/4 モデルが正常に検証されました
終了コード: 1
```

## 次のステップ

- [ ] 自動検出メカニズムを調査（inspect、pkgutil）
- [ ] アプローチ 1（スキャンと検証）のプロトタイプ
- [ ] repom 自身のモデルでテスト
- [ ] CLI インターフェースと出力フォーマットを設計
- [ ] CI/CD 用の JSON 出力オプションを検討
- [ ] 大規模モデルセットでのパフォーマンスを評価
- [ ] 詳細な実装計画のため `docs/research/` に移動

## 関連ドキュメント

- `docs/issue/completed/001_get_response_schema_forward_refs_improvement.md` - Phase 2 エラーハンドリング
- `README.md` - Phase 2 実装詳細
- `repom/base_model.py` - エラーハンドリング付き BaseModel 実装

## 解決すべき質問

1. 検証は EXEC_ENV を尊重すべきか（dev/prod の動作）？
2. 使用するプロジェクトのモデル vs. repom パッケージのモデルをどう扱うか？
3. 検証はテストスイートで自動的に実行すべきか？
4. 複雑な依存関係やデータベース接続を持つモデルはどうするか？
5. レスポンススキーマのみを検証すべきか、すべての Pydantic スキーマを検証すべきか？
