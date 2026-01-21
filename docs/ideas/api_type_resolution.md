# FastAPI/Flask での API 型解決

## ステータス
- **段階**: アイディア
- **優先度**: 低
- **複雑度**: 中
- **作成日**: 2025-11-14
- **最終更新**: 2025-11-14

## 概要

FastAPI/Flask のレスポンスモデルとして repom モデルを使用する際に、型を自動的に解決し、API ルート内での手動スキーマ生成を不要にします。

## モチベーション

API フレームワークで repom モデルを使用する場合:

**現在のワークフロー**（手動）:
```python
@app.get("/samples/{id}", response_model=Sample.get_response_schema())
def get_sample(id: int):
    return sample_repo.get_by_id(id)
```

**理想のワークフロー**（自動）:
```python
@app.get("/samples/{id}", response_model=Sample)
def get_sample(id: int) -> Sample:
    return sample_repo.get_by_id(id)
```

**現在のアプローチの問題点**:
- すべてのルートで `get_response_schema()` を呼び出す必要がある
- 冗長でエラーが発生しやすい
- 型ヒントが実際の戻り値の型と一致しない
- 標準的な FastAPI パターンと一貫性がない

**自動解決の利点**:
- よりクリーンで慣用的なコード
- IDE 向けの正しい型ヒント
- ボイラープレートの削減
- 標準的な FastAPI パターンが自然に動作

## ユースケース

### 1. FastAPI 統合
```python
from fastapi import FastAPI
from repom.integrations.fastapi import use_repom_models

app = FastAPI()
use_repom_models(app)  # 自動解決を有効化

@app.get("/samples/{id}", response_model=Sample)
def get_sample(id: int) -> Sample:
    return sample_repo.get_by_id(id)
# FastAPI が自動的に Sample.get_response_schema() を呼び出す
```

### 2. Flask 統合
```python
from flask import Flask
from repom.integrations.flask import RepomSchema

app = Flask(__name__)
schema = RepomSchema(app)

@app.route("/samples/<int:id>")
@schema.response(Sample)
def get_sample(id: int):
    return sample_repo.get_by_id(id)
```

### 3. OpenAPI ドキュメント自動生成
```python
# OpenAPI ドキュメントが正しいスキーマで自動生成される
# 手動でスキーマを指定する必要なし
@app.get("/samples/", response_model=list[Sample])
def list_samples() -> list[Sample]:
    return sample_repo.get_all()
```

## 検討可能なアプローチ

### アプローチ 1: FastAPI レスポンスモデルフック
**説明**: FastAPI のレスポンスモデル解決をインターセプト

**長所**:
- 既存の FastAPI パターンと連携
- ルート定義の変更不要
- 開発者にとって透過的

**短所**:
- FastAPI 固有の実装が必要
- FastAPI のアップデートと競合する可能性
- 複雑な統合ポイント

**例**:
```python
# repom/integrations/fastapi.py
from fastapi import FastAPI
from repom.models import BaseModel

def use_repom_models(app: FastAPI):
    original_add_api_route = app.add_api_route
    
    def wrapped_add_api_route(*args, **kwargs):
        response_model = kwargs.get('response_model')
        if response_model and issubclass(response_model, BaseModel):
            kwargs['response_model'] = response_model.get_response_schema()
        return original_add_api_route(*args, **kwargs)
    
    app.add_api_route = wrapped_add_api_route
```

### アプローチ 2: カスタムデコレータ
**説明**: スキーマ解決を処理するデコレータを提供

**長所**:
- 明示的で明確
- フレームワーク非依存
- 実装が容易

**短所**:
- 追加のデコレータが必要
- 標準的な FastAPI パターンではない
- ボイラープレートが増える

**例**:
```python
from repom.integrations import repom_response

@app.get("/samples/{id}")
@repom_response(Sample)
def get_sample(id: int):
    return sample_repo.get_by_id(id)
```

### アプローチ 3: レスポンスクラスラッパー
**説明**: FastAPI の Response クラスをラップして repom モデルを処理

**長所**:
- FastAPI のレスポンスシステムと連携
- 複数のレスポンスタイプを処理可能
- FastAPI パターンを維持

**短所**:
- より複雑な実装
- カスタム Response クラスが必要

**例**:
```python
from repom.integrations.fastapi import RepomResponse

@app.get("/samples/{id}")
def get_sample(id: int) -> RepomResponse[Sample]:
    return sample_repo.get_by_id(id)
```

## 技術的考慮事項

### FastAPI 統合ポイント
- **ルート登録**: `add_api_route()` をインターセプト
- **レスポンスモデル解決**: レスポンスモデル処理にフックを追加
- **OpenAPI スキーマ生成**: スキーマがドキュメントに表示されることを保証
- **型バリデーション**: Pydantic のバリデーション動作を維持

### Flask 統合ポイント
- **ビューデコレータ**: レスポンススキーマ用のカスタムデコレータ
- **レスポンスシリアライゼーション**: SQLAlchemy モデルを辞書に変換
- **JSON エンコーディング**: カスタム型（datetime、JSON フィールド）を処理
- **エラーハンドリング**: Flask エラーハンドラーと統合

### 互換性の懸念
- **FastAPI バージョン**: 0.100+（現在のパターン）をサポート
- **Pydantic バージョン**: すでに Pydantic 2.x と互換性あり
- **型ヒント**: IDE 向けの正しい型ヒントを維持
- **ジェネリック型**: `list[Sample]`、`dict[str, Sample]` などを処理

### パフォーマンス
- スキーマ生成は `get_response_schema()` でキャッシュされる
- リクエストごとの追加オーバーヘッドなし
- ルート登録時の一度だけの解決

### エラーハンドリング
- Phase 2 エラーハンドリング（SchemaGenerationError）を使用
- アプリ起動時にフェイルファスト（dev モード）
- 本番環境では警告をログ出力
- 明確なエラーメッセージを提供

## 統合ポイント

### 影響を受けるコンポーネント
- **新規パッケージ**: `repom/integrations/`（FastAPI、Flask モジュール）
- `pyproject.toml` - オプショナル依存関係を追加
- `README.md` - 統合パターンをドキュメント化
- `repom/base_model.py` - 統合フックが必要になる可能性

### パッケージ構造例
```
repom/integrations/
├── __init__.py
├── fastapi.py              # FastAPI 統合
├── flask.py                # Flask 統合（将来）
└── common.py               # 共有ユーティリティ
```

### オプショナル依存関係
```toml
[tool.poetry.extras]
fastapi = ["fastapi>=0.100.0"]
flask = ["flask>=2.0.0"]
all = ["fastapi>=0.100.0", "flask>=2.0.0"]
```

### インストール
```bash
# FastAPI 統合付きでインストール
poetry add repom[fastapi]

# すべての統合付きでインストール
poetry add repom[all]
```

## 次のステップ

- [ ] FastAPI ルート登録の内部を調査
- [ ] アプローチ 1（レスポンスモデルフック）のプロトタイプ
- [ ] 様々なレスポンスタイプでテスト（単一、リスト、辞書）
- [ ] ジェネリック型でテスト（`list[Sample]`、`Optional[Sample]`）
- [ ] OpenAPI ドキュメント生成を検証
- [ ] FastAPI 依存性注入でテスト
- [ ] Flask 統合アプローチを検討
- [ ] 既存プロジェクトへの影響を評価
- [ ] 詳細な実装計画のため `docs/research/` に移動

## 関連ドキュメント

- `repom/base_model.py` - `get_response_schema()` を持つ BaseModel
- `README.md` - 現在の使用パターン
- FastAPI ドキュメント: [Response Model](https://fastapi.tiangolo.com/tutorial/response-model/)

## 解決すべき質問

1. これを別パッケージ（`repom-fastapi`）にすべきか、統合すべきか？
2. 複雑なリレーションシップ（結合、遅延読み込み）を持つモデルをどう扱うか？
3. FastAPI の `response_model_exclude`、`response_model_include` をサポートすべきか？
4. 非同期 vs 同期リポジトリメソッドをどう扱うか？
5. モデルから辞書への自動変換のためのミドルウェアを提供すべきか？
6. ネストされたモデルと循環参照をどう扱うか？
7. FastAPI のバックグラウンドタスクと repom モデルをサポートすべきか？

## 追加アイディア

### 自動変換のためのミドルウェア
SQLAlchemy インスタンスを Pydantic モデルに自動変換:
```python
from repom.integrations.fastapi import RepomMiddleware

app = FastAPI()
app.add_middleware(RepomMiddleware)

@app.get("/samples/{id}")
def get_sample(id: int):
    # SQLAlchemy インスタンスを返す - 自動的に変換される
    return sample_repo.get_by_id(id)
```

### 依存性注入ヘルパー
repom リポジトリを FastAPI の依存性と統合:
```python
from repom.integrations.fastapi import RepomDepends

@app.get("/samples/{id}")
def get_sample(
    id: int,
    repo: SampleRepository = RepomDepends()
):
    return repo.get_by_id(id)
```

### WebSocket サポート
WebSocket 接続で repom モデルを処理:
```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    sample = sample_repo.get_by_id(1)
    # WebSocket 用に自動的にシリアライズ
    await websocket.send_json(sample)
```

### GraphQL 統合
Strawberry/Ariadne GraphQL に拡張:
```python
import strawberry
from repom.integrations.graphql import from_repom_model

@strawberry.type
class SampleType(from_repom_model(Sample)):
    pass
```
