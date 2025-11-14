# 研究: forward_refs の自動解決

**ステータス**: 🔬 調査中（未実装）

**優先度**: 高（長期目標）

**作成日**: 2025-11-14

**目標**: ユーザーが `forward_refs` を手動指定せずに、完全自動でカスタム型を解決

---

## 🎯 ビジョン

### 理想的な使い方

```python
# ユーザーが何も指定しなくても動作
VoiceScriptResponse = VoiceScriptModel.get_response_schema()
# ↑ AssetItemResponse も VoiceScriptLineLogResponse も自動解決！
```

### 現状（Phase 1 & 2 実装後）

```python
# Phase 1: 標準型は自動解決（List, Dict, Optional など）
# Phase 2: エラーメッセージで未解決型を検出・提案

# カスタム型は手動指定が必要
VoiceScriptResponse = VoiceScriptModel.get_response_schema(
    forward_refs={
        'AssetItemResponse': AssetItemResponse,
        'VoiceScriptLineLogResponse': VoiceScriptLineLogResponse
    }
)
```

### Phase 2 で既に実装済みの機能

**エラー発生時の自動検出**:
- Pydantic エラーメッセージから未解決型を正規表現で抽出
- 具体的なコード例を自動生成
- 開発環境では例外、本番環境ではログで対応

```python
# Phase 2 実装済み
def _extract_undefined_types(error_message: str) -> Set[str]:
    """Pydantic エラーメッセージから未解決型を抽出"""
    pattern = r"name '([^']+)' is not defined"
    matches = re.findall(pattern, error_message)
    return set(matches)
```

**Phase 2 の利点**:
- ✅ エラーが**実際に発生した時点で**正確に検出
- ✅ Pydantic が判定した「本当に足りない型」だけを表示
- ✅ 偽陽性（False Positive）がない
- ✅ 具体的なコード例を自動生成

---

## 🔍 技術的課題

### 1. 型アノテーションの形式による難易度

#### パターンA: 直接型指定（検出可能）

```python
@BaseModel.response_field(
    items=List['BookResponse']  # ← __args__ で 'BookResponse' を取得可能
)
def to_dict(self):
    ...
```

**検出方法**:
```python
import typing
from typing import get_args

# List['BookResponse'] の場合
field_type = List['BookResponse']
if hasattr(field_type, '__args__'):
    for arg in field_type.__args__:
        if isinstance(arg, str):
            print(f"検出: {arg}")  # → "BookResponse"
```

#### パターンB: 文字列全体（検出困難）

```python
@BaseModel.response_field(
    items="List[BookResponse]"  # ← 文字列全体なので __args__ がない
)
def to_dict(self):
    ...
```

**問題点**:
- 型情報が単なる文字列なので、Python の型システムで解析できない
- ast モジュールで文字列をパースする必要がある
- 複雑な型表現（Union、Optional、ネスト）の完全なパースは困難

**ast モジュールでの解析例**:
```python
import ast

def parse_type_string(type_str: str) -> Set[str]:
    """文字列型アノテーションから型名を抽出"""
    try:
        tree = ast.parse(type_str, mode='eval')
        # AST を走査して型名を抽出
        # 例: "List[BookResponse]" → {'List', 'BookResponse'}
    except SyntaxError:
        # 不正な型表現
        return set()
```

#### パターンC: Union型（非常に困難）

```python
@BaseModel.response_field(
    item="BookResponse | None"  # ← Python 3.10+ の Union 構文
)
def to_dict(self):
    ...
```

**問題点**:
- `|` 演算子は Python 3.10+ の新しい構文
- ast でのパースが複雑
- `Optional[BookResponse]` との互換性を保つ必要がある

### 2. 名前空間の問題

#### 課題: 型名から実際のクラスを取得する方法

```python
# 文字列 'BookResponse' から実際のクラスを取得したい
detected_types = {'BookResponse', 'AssetItemResponse'}

# どこから取得する？
# 1. グローバル名前空間？ → import の順序に依存
# 2. モジュールのインポート？ → モジュール名が不明
# 3. 動的インポート？ → セキュリティリスク
```

**アプローチ1: グローバル名前空間から取得**
```python
import sys

def resolve_type(type_name: str):
    # 呼び出し元のモジュールの名前空間を取得
    frame = sys._getframe(1)
    namespace = frame.f_globals
    
    if type_name in namespace:
        return namespace[type_name]
    else:
        raise NameError(f"Type '{type_name}' not found")
```

**問題点**:
- 呼び出し元のコンテキストに依存
- モジュール境界を越えられない
- テストが困難

**アプローチ2: 動的インポート**
```python
import importlib

def resolve_type(type_name: str, module_name: str):
    module = importlib.import_module(module_name)
    return getattr(module, type_name)
```

**問題点**:
- モジュール名をどう決定するか？
- セキュリティリスク（任意コード実行）
- import エラーの処理が複雑

### 3. 循環インポートの問題

```python
# models/book.py
from models.review import ReviewResponse  # ← 循環インポート

class BookModel(BaseModel):
    @response_field(reviews=List['ReviewResponse'])
    def to_dict(self): ...

# models/review.py
from models.book import BookResponse  # ← 循環インポート

class ReviewModel(BaseModel):
    @response_field(book='BookResponse')
    def to_dict(self): ...
```

**問題点**:
- Python は循環インポートを許可するが、実行時エラーになる場合がある
- スキーマ生成の順序に依存
- 文字列型アノテーションで循環参照を避ける必要がある

---

## 💡 アプローチ候補

### アプローチ1: レジストリパターン

**概要**: グローバルレジストリに全スキーマを登録し、必要に応じて取得

```python
# グローバルレジストリ
_SCHEMA_REGISTRY: Dict[str, Type[BaseModel]] = {}

class BaseModel:
    @classmethod
    def get_response_schema(cls, schema_name: str = None):
        if schema_name is None:
            schema_name = f"{cls.__name__}Response"
        
        # 既にレジストリにある場合は返す
        if schema_name in _SCHEMA_REGISTRY:
            return _SCHEMA_REGISTRY[schema_name]
        
        # スキーマを生成
        schema = create_model(...)
        
        # レジストリに登録
        _SCHEMA_REGISTRY[schema_name] = schema
        
        # 前方参照を解決（レジストリから取得）
        detected_refs = _extract_forward_refs_from_fields(schema)
        forward_refs = {
            name: _SCHEMA_REGISTRY[name]
            for name in detected_refs
            if name in _SCHEMA_REGISTRY
        }
        
        # model_rebuild で解決
        schema.model_rebuild(_types_namespace=forward_refs)
        
        return schema
```

**利点**:
- ✅ シンプルな実装
- ✅ 循環参照に対応可能
- ✅ スキーマの再利用が容易

**欠点**:
- ⚠️ スキーマ生成の順序に依存
- ⚠️ 最初の呼び出しで依存スキーマが未登録の場合、解決できない
- ⚠️ グローバル状態（テストの独立性に影響）

**解決策: 2パス方式**
```python
# 1st pass: すべてのスキーマを未解決のまま生成・登録
for model in all_models:
    model.get_response_schema(_skip_rebuild=True)

# 2nd pass: すべてのスキーマの前方参照を解決
for schema in _SCHEMA_REGISTRY.values():
    resolve_forward_refs(schema)
```

### アプローチ2: 遅延解決パターン

**概要**: 初回は未解決のまま生成し、必要に応じて依存を動的に解決

```python
class BaseModel:
    @classmethod
    def get_response_schema(cls, _resolving=False):
        schema = create_model(...)
        
        if not _resolving:
            # 前方参照を検出
            detected_refs = _extract_forward_refs_from_fields(schema)
            
            # 依存スキーマを生成（再帰的）
            forward_refs = {}
            for ref_name in detected_refs:
                ref_model = _find_model_by_schema_name(ref_name)
                if ref_model:
                    forward_refs[ref_name] = ref_model.get_response_schema(
                        _resolving=True
                    )
            
            # model_rebuild で解決
            schema.model_rebuild(_types_namespace=forward_refs)
        
        return schema
```

**利点**:
- ✅ 自動的に依存を解決
- ✅ ユーザーが何も指定しなくても動作

**欠点**:
- ⚠️ `_find_model_by_schema_name()` の実装が困難
- ⚠️ 循環参照の検出が必要
- ⚠️ 動的インポートのセキュリティリスク

### アプローチ3: デコレータパターン

**概要**: モデル定義時にデコレータで自動登録

```python
# レジストリ
_MODEL_REGISTRY: Dict[str, Type[BaseModel]] = {}

def register_response_schema(cls):
    """モデルを自動登録するデコレータ"""
    schema_name = f"{cls.__name__}Response"
    _MODEL_REGISTRY[schema_name] = cls
    return cls

# 使用例
@register_response_schema
class BookModel(BaseModel):
    __tablename__ = 'books'
    ...

@register_response_schema
class ReviewModel(BaseModel):
    __tablename__ = 'reviews'
    ...

# get_response_schema() 呼び出し時に自動解決
BookResponse = BookModel.get_response_schema()  # 自動的に依存を解決
```

**利点**:
- ✅ 明示的な登録（デコレータ）
- ✅ すべてのモデルが登録される保証
- ✅ レジストリパターンとの親和性が高い

**欠点**:
- ⚠️ すべてのモデルにデコレータを付ける必要がある
- ⚠️ 既存コードの変更が必要

### アプローチ4: Phase 2 拡張（提案2の実装）

**概要**: Phase 2 の未解決型検出を拡張し、エラー発生前に警告

```python
def _extract_forward_refs_from_annotations(field_definitions: dict) -> Set[str]:
    """フィールド定義から前方参照（文字列）を抽出（エラー前）"""
    refs = set()
    for field_type in field_definitions.values():
        # パターンA: List['BookResponse'] の検出
        if hasattr(field_type, '__args__'):
            for arg in field_type.__args__:
                if isinstance(arg, str):
                    refs.add(arg)
        
        # パターンB: "List[BookResponse]" の検出（ast使用）
        if isinstance(field_type, str):
            refs.update(_parse_type_string(field_type))
    
    return refs

def get_response_schema(cls, forward_refs=None):
    # ... スキーマ生成 ...
    
    # エラー前に警告
    detected = _extract_forward_refs_from_annotations(field_definitions)
    if detected and not forward_refs:
        import warnings
        warnings.warn(
            f"Detected forward references: {detected}. "
            f"Consider providing forward_refs parameter."
        )
    
    # ... 以下 Phase 2 と同じ ...
```

**利点**:
- ✅ Phase 2 との互換性
- ✅ 段階的な実装が可能
- ✅ エラー前に問題を検出

**欠点**:
- ⚠️ パターンB（文字列全体）の検出が困難
- ⚠️ 偽陽性（False Positive）の可能性
- ⚠️ Phase 2 と重複する警告

---

## 🧪 実験的実装の計画

### Step 1: レジストリの基本実装（短期）

```python
# repom/schema_registry.py
_SCHEMA_REGISTRY: Dict[str, Type[BaseModel]] = {}

def register_schema(name: str, schema: Type[BaseModel]):
    _SCHEMA_REGISTRY[name] = schema

def get_schema(name: str) -> Optional[Type[BaseModel]]:
    return _SCHEMA_REGISTRY.get(name)

def clear_registry():
    """テスト用"""
    _SCHEMA_REGISTRY.clear()
```

**テスト**:
```python
def test_registry_basic():
    register_schema('BookResponse', BookResponse)
    assert get_schema('BookResponse') is BookResponse
    
    clear_registry()
    assert get_schema('BookResponse') is None
```

### Step 2: パターンA の自動検出（中期）

```python
def _extract_forward_refs_pattern_a(field_definitions: dict) -> Set[str]:
    """List['Type'] 形式の検出"""
    refs = set()
    for field_type in field_definitions.values():
        if hasattr(field_type, '__args__'):
            for arg in field_type.__args__:
                if isinstance(arg, str):
                    refs.add(arg)
    return refs
```

**テスト**:
```python
def test_detect_pattern_a():
    field_defs = {
        'items': List['BookResponse']
    }
    refs = _extract_forward_refs_pattern_a(field_defs)
    assert refs == {'BookResponse'}
```

### Step 3: レジストリからの自動解決（中期）

```python
def get_response_schema(cls, forward_refs=None, auto_resolve=True):
    # ... スキーマ生成 ...
    
    if auto_resolve:
        # パターンA の前方参照を検出
        detected = _extract_forward_refs_pattern_a(field_definitions)
        
        # レジストリから自動取得
        auto_refs = {
            name: get_schema(name)
            for name in detected
            if get_schema(name) is not None
        }
        
        # ユーザー指定と統合
        if forward_refs:
            auto_refs.update(forward_refs)
        
        forward_refs = auto_refs
    
    # ... model_rebuild ...
```

### Step 4: パターンB の解析（長期）

```python
import ast

def _parse_type_string(type_str: str) -> Set[str]:
    """文字列型アノテーションから型名を抽出"""
    refs = set()
    try:
        tree = ast.parse(type_str, mode='eval')
        
        # AST を走査して Name ノードを抽出
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                refs.add(node.id)
    except SyntaxError:
        pass
    
    return refs
```

**テスト**:
```python
def test_parse_type_string():
    assert _parse_type_string("List[BookResponse]") == {'List', 'BookResponse'}
    assert _parse_type_string("BookResponse | None") == {'BookResponse', 'None'}
    assert _parse_type_string("Dict[str, BookResponse]") == {'Dict', 'str', 'BookResponse'}
```

### Step 5: 完全自動化（長期）

- 動的インポートの実装
- 循環参照の解決
- エラーハンドリングの強化
- パフォーマンス最適化

---

## 🤔 検討事項

### セキュリティ

**動的インポートのリスク**:
```python
# 危険な例
type_name = user_input  # ユーザー入力
module = importlib.import_module(type_name)  # 任意モジュール実行
```

**対策**:
- ホワイトリスト方式（登録されたモジュールのみ）
- サンドボックス化
- 信頼できないコードの実行防止

### パフォーマンス

**レジストリのメモリ使用量**:
- すべてのスキーマをメモリに保持
- 大規模プロジェクトでのメモリ消費

**遅延解決のオーバーヘッド**:
- 再帰的なスキーマ生成
- キャッシュ戦略の最適化

### 互換性

**既存コードとの互換性**:
- Phase 1 & 2 で実装した機能が動き続けること
- `forward_refs` パラメータの動作を変更しない
- 段階的な移行パス

**テストの独立性**:
- グローバルレジストリの影響
- テスト間での状態の持ち越し
- `clear_registry()` の適切な使用

---

## 📊 実装の優先度

### 完了済み

1. ✅ **Phase 1**: 標準型の自動解決（2025-11-14）
2. ✅ **Phase 2**: エラーメッセージ改善 + 未解決型の自動検出（2025-11-14）

### 次のステップ

3. 📝 **Phase 3**: ドキュメント改善（短期）
4. 🔬 **Step 1**: レジストリの基本実装（中期）
5. 🔬 **Step 2-3**: パターンA の自動検出 + 自動解決（中期）
6. 🔬 **Step 4**: パターンB の解析（長期）
7. 🔬 **Step 5**: 完全自動化（長期）

---

## 💭 Phase 2 との関係

### Phase 2 で既に解決されている課題

- ✅ 未解決型の検出（エラーメッセージから正規表現で抽出）
- ✅ 具体的なコード例の自動生成
- ✅ 開発環境と本番環境の使い分け
- ✅ 偽陽性（False Positive）がない

### この研究で追加したい機能

- 🔬 エラー発生**前**の検出（予防的）
- 🔬 レジストリによる自動解決
- 🔬 ユーザーが何も指定しなくても動作（完全自動化）

### Phase 2 を拡張すべきか？

**提案2（エラー前の警告）の実装判断**:

❌ **実装しない方が良い理由**:
- Phase 2 で十分カバーしている
- 偽陽性のリスク
- 実装コストが高い
- パターンB（文字列全体）の検出が困難

✅ **代わりにレジストリパターンを優先**:
- より確実な自動解決
- Phase 2 と相互補完的
- 段階的な実装が可能

---

## 📚 関連リソース

### 実装済み機能

- **Phase 1**: [docs/issue/get_response_schema_forward_refs_improvement.md](../issue/get_response_schema_forward_refs_improvement.md)
- **Phase 2**: 同上

### 関連ドキュメント

- **技術詳細**: [docs/get_response_schema_technical.md](../get_response_schema_technical.md)
- **README**: FastAPI 統合セクション

### 参考資料

- Pydantic 公式ドキュメント: https://docs.pydantic.dev/
- Python ast モジュール: https://docs.python.org/3/library/ast.html
- FastAPI 公式ドキュメント: https://fastapi.tiangolo.com/

---

**最終更新**: 2025-11-14

**次のアクション**: Step 1（レジストリの基本実装）の実験的実装を検討
