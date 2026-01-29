# QueryAnalyzer ガイド - N+1問題検出ツール

## 概要

`QueryAnalyzer` は、SQLAlchemy クエリを監視して N+1 問題を検出するためのツールです。実際のクエリログを収集し、実行されたクエリの回数と種類を分析します。

## 主な機能

- ✅ **クエリキャプチャ**: SQLAlchemy が実行する全てのクエリを記録
- ✅ **N+1 問題検出**: 繰り返し実行されるクエリパターンを検出
- ✅ **統計レポート**: クエリタイプごとの実行回数を集計
- ✅ **詳細ログ**: verbose モードで全クエリの内容を表示
- ✅ **モデル確認**: 文字列からモデルクラスを取得するヘルパー関数

## 基本的な使い方

### 1. インポート

```python
from repom.scripts.query_analyzer import QueryAnalyzer
from repom.database import get_db_session
from myapp.models import User
```

### 2. クエリの監視

```python
analyzer = QueryAnalyzer()

with analyzer.capture():
    # ここで実行されるクエリが記録される
    users = session.query(User).all()
    for user in users:
        print(user.posts)  # N+1 問題が発生する可能性

# 分析結果を表示
analyzer.print_report()
```

### 3. レポートの出力例

```
======================================================================
Query Analysis Report
======================================================================

Total Queries: 11

Query Type Breakdown:
  BEGIN: 1
  SELECT: 10

⚠️  Potential N+1 Problem Detected!
   Found 1 repeated query patterns

Repeated Query Patterns:

  Pattern (repeated 10 times):
    SELECT test_posts.id, test_posts.user_id, test_posts.title FROM test_posts WHERE test_posts.user_id = ?

======================================================================
```

## 実践例

### 例1: N+1 問題の検出

```python
from repom.scripts.query_analyzer import QueryAnalyzer
from repom import BaseRepository
from repom.database import get_db_session
from myapp.models import Author

analyzer = QueryAnalyzer()
repo = BaseRepository(Author)

with analyzer.capture():
    # 全著者を取得
    authors = repo.get_all()
    
    # 各著者の本にアクセス（N+1 問題発生）
    for author in authors:
        print(f"{author.name}: {len(author.books)} books")

analyzer.print_report()
```

**出力:**
```
Total Queries: 11
Query Type Breakdown:
  SELECT: 11

⚠️  Potential N+1 Problem Detected!
   Found 1 repeated query patterns
```

### 例2: Eager Loading で解決

```python
from sqlalchemy.orm import joinedload

analyzer = QueryAnalyzer()

with analyzer.capture():
    # joinedload で本も一緒に取得
    authors = session.query(Author).options(joinedload(Author.books)).all()
    
    for author in authors:
        print(f"{author.name}: {len(author.books)} books")

analyzer.print_report()
```

**出力:**
```
Total Queries: 1
Query Type Breakdown:
  SELECT: 1

✅ No obvious N+1 problems detected
```

### 例3: BaseRepository の default_options を使う

```python
from repom import BaseRepository
from sqlalchemy.orm import joinedload

class AuthorRepository(BaseRepository[Author]):
    def __init__(self, session=None):
        super().__init__(Author, session)
        # デフォルトで books を eager load
        self.default_options = [joinedload(Author.books)]

analyzer = QueryAnalyzer()
repo = AuthorRepository()

with analyzer.capture():
    authors = repo.get_all()
    for author in authors:
        print(f"{author.name}: {len(author.books)} books")

analyzer.print_report()  # N+1 問題なし
```

### 例4: 詳細ログの表示

```python
analyzer = QueryAnalyzer()

with analyzer.capture():
    users = session.query(User).limit(3).all()

# verbose=True で全クエリの内容を表示
analyzer.print_report(verbose=True)
```

**出力:**
```
======================================================================
Query Analysis Report
======================================================================

Total Queries: 1

Query Type Breakdown:
  SELECT: 1

✅ No obvious N+1 problems detected

----------------------------------------------------------------------
All Captured Queries:
----------------------------------------------------------------------

1. [SELECT]
   SELECT users.id, users.name, users.email FROM users  LIMIT ? OFFSET ?

======================================================================
```

## API リファレンス

### QueryAnalyzer クラス

```python
class QueryAnalyzer:
    def __init__(self, engine: Optional[Engine] = None)
```

**パラメータ:**
- `engine` (Optional[Engine]): 監視する SQLAlchemy エンジン。省略時はデフォルトエンジンを使用

### ヘルパー関数

#### get_model_by_name()

```python
def get_model_by_name(model_name: str) -> Optional[Type]
```

指定した文字列からモデルクラスを取得。

**パラメータ:**
- `model_name` (str): モデル名（例: 'User', 'Author'）

**戻り値:**
- モデルクラス、見つからない場合は None

**使用例:**
```python
from repom.scripts.query_analyzer import get_model_by_name

User = get_model_by_name('User')
if User:
    print(f"Found model: {User.__tablename__}")
```

#### list_all_models()

```python
def list_all_models() -> List[str]
```

登録されている全てのモデル名を取得。

**戻り値:**
- モデル名のリスト（ソート済み）

**使用例:**
```python
from repom.scripts.query_analyzer import list_all_models

models = list_all_models()
print(f"Available models: {', '.join(models)}")
```

#### set_target_model()

```python
def set_target_model(self, model: Union[str, Type]) -> None
```

特定のモデルをターゲットとして設定（将来的な機能拡張用）。

**パラメータ:**
- `model`: モデル名（文字列）またはモデルクラス

**使用例:**
```python
analyzer = QueryAnalyzer()
analyzer.set_target_model('User')
# または
analyzer.set_target_model(User)
```

### capture() メソッド

```python
@contextmanager
def capture(self, model: Optional[Union[str, Type]] = None)
```

クエリをキャプチャするコンテキストマネージャー。

**パラメータ:**
- `model` (Optional): ターゲットモデル（文字列またはクラス）を指定可能

**使用例:**
```python
# モデルを指定してキャプチャ
with analyzer.capture(model='User'):
    users = session.query(User).all()

# または
with analyzer.capture():
    users = session.query(User).all()
```

### print_report() メソッド

```python
def print_report(self, verbose: bool = False) -> None
```

分析結果をコンソールに表示。

**パラメータ:**
- `verbose` (bool): True の場合、全クエリの内容を表示

### analyze_n_plus_1() メソッド

```python
def analyze_n_plus_1(self) -> dict
```

N+1 問題を分析して結果を辞書で返す。

**戻り値:**
```python
{
    'total_queries': int,        # 総クエリ数
    'select_queries': int,       # SELECT クエリ数
    'potential_n_plus_1': bool,  # N+1 問題の可能性
    'repeated_queries': dict,    # 繰り返されたクエリパターン
    'query_stats': dict          # クエリタイプごとの統計
}
```

### get_queries() メソッド

```python
def get_queries(self) -> List[dict]
```

キャプチャした全クエリを取得。

**戻り値:**
```python
[
    {
        'statement': str,   # SQL 文
        'type': str,        # クエリタイプ (SELECT, INSERT, など)
        'parameters': Any   # クエリパラメータ
    },
    ...
]
```

### get_stats() メソッド

```python
def get_stats(self) -> dict
```

クエリ統計を取得。

**戻り値:**
```python
{
    'SELECT': 10,
    'INSERT': 2,
    'UPDATE': 1,
    ...
}
```

## 使用シナリオ

### モデル名から動的に分析

```python
from repom.scripts.query_analyzer import QueryAnalyzer, get_model_by_name

# モデル名が文字列で与えられた場合
model_name = 'User'
UserModel = get_model_by_name(model_name)

if UserModel:
    analyzer = QueryAnalyzer()
    with analyzer.capture(model=model_name):
        # UserModel を使ったクエリ
        users = session.query(UserModel).all()
    
    analyzer.print_report()
else:
    print(f"Model '{model_name}' not found")
```

### 利用可能なモデル一覧を確認

```python
from repom.scripts.query_analyzer import list_all_models

# 全モデルを表示
models = list_all_models()
print(f"Available models ({len(models)}):")
for model in models:
    print(f"  - {model}")
```

### 開発中の確認

```python
# 開発中にコードの特定部分を分析
analyzer = QueryAnalyzer()

with analyzer.capture():
    result = my_function_that_queries_db()

analyzer.print_report()
```

### テストでの使用

```python
def test_no_n_plus_1_in_user_list(db_test):
    """ユーザー一覧取得で N+1 問題が発生しないことを確認"""
    analyzer = QueryAnalyzer(engine=db_test.bind.engine)
    
    with analyzer.capture():
        users = get_user_list_with_posts()
    
    analysis = analyzer.analyze_n_plus_1()
    
    # N+1 問題がないことをアサート
    assert analysis['potential_n_plus_1'] is False
    # クエリ数が期待値以下であることを確認
    assert analysis['total_queries'] <= 3
```

### プロジェクトでの使用

外部プロジェクト（例: mine-py）から利用する場合:

```python
# mine-py/src/mine_py/debug.py
from repom.scripts.query_analyzer import QueryAnalyzer
from mine_py.repositories import UserRepository

def analyze_user_query():
    analyzer = QueryAnalyzer()
    repo = UserRepository()
    
    with analyzer.capture():
        users = repo.get_all()
        for user in users:
            print(f"{user.name}: {len(user.posts)} posts")
    
    analyzer.print_report(verbose=True)

if __name__ == '__main__':
    analyze_user_query()
```

## ベストプラクティス

### 1. 開発中の継続的なチェック

N+1 問題は気づかないうちに発生しやすいため、新しい機能を実装するたびにチェックすることを推奨します。

```python
# 新機能実装後
analyzer = QueryAnalyzer()
with analyzer.capture():
    test_new_feature()
analyzer.print_report()
```

### 2. BaseRepository の default_options を活用

頻繁にアクセスするリレーションは、リポジトリで事前定義しておきます。

```python
class UserRepository(BaseRepository[User]):
    def __init__(self, session=None):
        super().__init__(User, session)
        self.default_options = [
            joinedload(User.posts),
            joinedload(User.profile)
        ]
```

### 3. テストで N+1 を防止

重要なエンドポイントやクエリには、N+1 問題が発生しないことを保証するテストを追加します。

```python
def test_api_endpoint_performance(client, db_test):
    analyzer = QueryAnalyzer(engine=db_test.bind.engine)
    
    with analyzer.capture():
        response = client.get('/api/users')
    
    assert response.status_code == 200
    analysis = analyzer.analyze_n_plus_1()
    assert analysis['total_queries'] <= 5  # 閾値を設定
```

## 制限事項と注意点

### 1. 検出の限界

`QueryAnalyzer` は繰り返しパターンを検出しますが、全ての N+1 問題を検出できるわけではありません。以下のような場合は人間による判断が必要です:

- 意図的に複数クエリを実行している場合
- パラメータが異なる正当な複数クエリ
- 複雑なクエリ最適化が必要な場合

### 2. パフォーマンス

`QueryAnalyzer` はイベントリスナーを使ってクエリを記録するため、わずかなオーバーヘッドがあります。本番環境では使用しないでください。

### 3. テスト環境での使用

テストで使用する場合、`db_test` フィクスチャのエンジンを明示的に渡す必要があります:

```python
# ✅ 正しい
analyzer = QueryAnalyzer(engine=db_test.bind.engine)

# ❌ 誤り（デフォルトエンジンを使ってしまう）
analyzer = QueryAnalyzer()
```

## まとめ

`QueryAnalyzer` は N+1 問題を早期に発見し、パフォーマンス問題を未然に防ぐための強力なツールです。開発プロセスに組み込むことで、データベースクエリの最適化を継続的に行うことができます。

## 関連ドキュメント

- [BaseRepository Guide](../repository/base_repository_guide.md) - リポジトリの基本的な使い方
- [Repository Advanced Guide](../repository/repository_advanced_guide.md) - Eager Loading の詳細
- [Testing Guide](../testing/testing_guide.md) - テストでの使用方法
