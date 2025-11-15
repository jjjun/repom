# スキーマファイル生成

## ステータス
- **段階**: アイディア
- **優先度**: 低
- **複雑度**: 低
- **作成日**: 2025-11-14
- **最終更新**: 2025-11-14

## 概要

repom モデルから JSON Schema ファイルを生成し、API ドキュメントツール、契約テスト、フロントエンド TypeScript 生成をサポートします。

## モチベーション

repom モデルで API を構築する際、開発者は以下を必要とすることが多いです:
- **OpenAPI/Swagger ドキュメント**: API 仕様用の JSON スキーマ
- **フロントエンドの型**: スキーマから TypeScript インターフェースを生成
- **契約テスト**: スキーマに対して API レスポンスを検証
- **外部統合**: 非 Python サービスとスキーマを共有

現在:
- スキーマは Python コード内にのみ存在
- JSON Schema ファイルを手動で作成する必要がある
- モデルとスキーマ間の自動同期がない

スキーマファイル生成により:
- スキーマを自動的にファイルにエクスポート
- ドキュメントをモデルと同期させる
- ツール統合を可能にする（OpenAPI、TypeScript ジェネレータ）

## ユースケース

### 1. OpenAPI ドキュメント
```bash
# API ドキュメント用のスキーマを生成
poetry run repom generate-schemas --output schemas/

# OpenAPI 仕様で使用
# openapi.yml が schemas/Sample.json を参照
```

### 2. フロントエンド TypeScript 生成
```bash
# スキーマを生成
poetry run repom generate-schemas --output schemas/

# TypeScript に変換
npx json-schema-to-typescript schemas/*.json --output src/types/
```

### 3. 契約テスト
```python
# 生成されたスキーマに対して API レスポンスを検証
import json
from jsonschema import validate

with open('schemas/Sample.json') as f:
    schema = json.load(f)
    
validate(api_response, schema)  # レスポンスがモデルと一致することを確認
```

## 検討可能なアプローチ

### アプローチ 1: Pydantic の model_json_schema()
**説明**: Pydantic のビルトイン JSON Schema エクスポートを使用

**長所**:
- ネイティブな Pydantic サポート
- 標準的な JSON Schema フォーマット
- カスタムシリアライゼーション不要

**短所**:
- repom のカスタム型をうまく扱えない可能性
- TypeDecorator でのテストが必要

**例**:
```python
schema = MyModel.get_response_schema().model_json_schema()
with open('schemas/MyModel.json', 'w') as f:
    json.dump(schema, f, indent=2)
```

### アプローチ 2: カスタムスキーマシリアライザ
**説明**: repom 固有の型のためのカスタムシリアライゼーションを構築

**長所**:
- 出力フォーマットの完全な制御
- カスタム TypeDecorator を処理可能
- repom 固有のメタデータを追加可能

**短所**:
- 実装作業が増える
- シリアライゼーションロジックの保守が必要

**例**:
```python
def serialize_schema(model_cls: Type[BaseModel]) -> dict:
    schema = model_cls.get_response_schema().model_json_schema()
    # repom 型のカスタムハンドリングを追加
    schema = enhance_custom_types(schema)
    return schema
```

### アプローチ 3: テンプレート付き CLI
**説明**: カスタマイズ可能なテンプレートでスキーマを生成

**長所**:
- 柔軟な出力フォーマット
- 複数のフォーマット（JSON Schema、OpenAPI など）を生成可能
- テンプレートベースのカスタマイズ

**短所**:
- より複雑な実装
- テンプレートの保守

**例**:
```bash
poetry run repom generate-schemas \
  --format json-schema \
  --template openapi \
  --output schemas/
```
```

## Potential Approaches

### Approach 1: Pydantic's model_json_schema()
**Description**: Use Pydantic's built-in JSON Schema export

**Pros**:
- Native Pydantic support
- Standard JSON Schema format
- No custom serialization needed

**Cons**:
- May not handle repom's custom types well
- Requires testing with TypeDecorators

**Example**:
```python
schema = MyModel.get_response_schema().model_json_schema()
with open('schemas/MyModel.json', 'w') as f:
    json.dump(schema, f, indent=2)
```

### Approach 2: Custom Schema Serializer
**Description**: Build custom serialization for repom-specific types

**Pros**:
- Full control over output format
- Can handle custom TypeDecorators
- Can add repom-specific metadata

**Cons**:
- More implementation work
- Must maintain serialization logic

**Example**:
```python
def serialize_schema(model_cls: Type[BaseModel]) -> dict:
    schema = model_cls.get_response_schema().model_json_schema()
    # Add custom handling for repom types
    schema = enhance_custom_types(schema)
    return schema
```

### Approach 3: CLI with Templates
**Description**: Generate schemas with customizable templates

**Pros**:
- Flexible output format
- Can generate multiple formats (JSON Schema, OpenAPI, etc.)
- Template-based customization

**Cons**:
- More complex implementation
- Template maintenance

**Example**:
```bash
poetry run repom generate-schemas \
  --format json-schema \
  --template openapi \
  --output schemas/
```

## 技術的考慮事項

### カスタム型の処理
repom はうまくシリアライズされない可能性があるカスタム TypeDecorator を使用:
- `ISO8601DateTime` → ISO 8601 文字列フォーマットとしてエクスポート
- `JSONEncoded` → オブジェクト型としてエクスポート
- `ListJSON` → 配列型としてエクスポート
- `CreatedAt` → datetime 文字列としてエクスポート

**解決策**: 各 TypeDecorator にカスタムシリアライゼーションルールを追加

### ファイル構成
```
schemas/
├── Sample.json                 # 個別モデルのスキーマ
├── UserSession.json
├── combined.json              # すべてのスキーマを1つのファイルに（オプショナル）
└── openapi/                   # OpenAPI 固有のフォーマット（オプショナル）
    └── components.yml
```

### スキーマフォーマットオプション
- **JSON Schema Draft 7/2020**: 標準フォーマット
- **OpenAPI 3.0/3.1**: API 固有のフォーマット
- **TypeScript**: 直接 TS インターフェース生成

### 依存関係
- **jsonschema**: バリデーションとスキーマ操作
- **pyyaml**（オプショナル）: YAML 出力フォーマット
- 追加の重い依存関係なし

## 統合ポイント

### 影響を受けるコンポーネント
- `repom/scripts/` - 新規スクリプト: `generate_schemas.py`
- `pyproject.toml` - Poetry スクリプトエントリーポイントを追加
- `repom/base_model.py` - スキーマシリアライゼーションヘルパーの可能性
- `README.md` - 新しいコマンドをドキュメント化

### 既存機能との相互作用
- `BaseModel.get_response_schema()` を使用
- Phase 2 エラーハンドリングと互換性あり
- すべての repom カスタム型と動作

### コマンド例
```bash
# すべてのスキーマを生成
poetry run repom generate-schemas

# 特定のモデルを生成
poetry run repom generate-schemas Sample UserSession

# 出力ディレクトリを指定
poetry run repom generate-schemas --output ./api/schemas/

# 異なるフォーマット
poetry run repom generate-schemas --format openapi-yaml
```

### 出力例
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Sample",
  "type": "object",
  "properties": {
    "id": {
      "type": "integer",
      "description": "Primary key"
    },
    "name": {
      "type": "string",
      "maxLength": 100
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 datetime"
    }
  },
  "required": ["name"]
}
```

## 次のステップ

- [ ] Pydantic の `model_json_schema()` 出力フォーマットを調査
- [ ] repom のカスタム TypeDecorator でテスト
- [ ] 基本的なスキーマ生成のプロトタイプ
- [ ] カスタムシリアライゼーションの必要性を評価
- [ ] CLI インターフェース設計（引数、出力フォーマット）
- [ ] OpenAPI ツールと TypeScript ジェネレータでテスト
- [ ] 自動再生成のためのウォッチモードを検討
- [ ] 実装する場合は `docs/research/` に移動

## 関連ドキュメント

- `repom/custom_types/` - カスタム型の実装
- `README.md` - BaseModel ドキュメント
- Pydantic ドキュメント: [JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/)

## 解決すべき質問

1. スキーマをバージョン管理にコミットすべきか？
2. 使用するプロジェクトに最適なフォーマットは何か（JSON vs YAML）？
3. 増分生成（変更されたモデルのみ）をサポートすべきか？
4. モデル間のリレーションシップ（外部キー）をどう扱うか？
5. データベース固有のメタデータ（テーブル名、インデックス）を含めるべきか？
6. スキーマにバリデーションルール（最小/最大、パターン）を含めるべきか？
7. 循環参照を持つモデルをどう扱うか？

## 追加アイディア

### スキーマバージョニング
API 互換性のためにスキーマバージョンを追跡:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Sample",
  "version": "1.0.0",
  "deprecated": false,
  "properties": { ... }
}
```

### ドキュメント統合
スキーマから markdown ドキュメントを生成:
```bash
poetry run repom generate-docs --from-schemas
```

### ウォッチモード
ファイル変更時にスキーマを自動再生成:
```bash
poetry run repom generate-schemas --watch
```
