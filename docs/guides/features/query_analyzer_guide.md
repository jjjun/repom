# QueryAnalyzer 繧ｬ繧､繝・- N+1蝠城｡梧､懷・繝・・繝ｫ

## 讎りｦ・

`QueryAnalyzer` 縺ｯ縲ヾQLAlchemy 繧ｯ繧ｨ繝ｪ繧堤屮隕悶＠縺ｦ N+1 蝠城｡後ｒ讀懷・縺吶ｋ縺溘ａ縺ｮ繝・・繝ｫ縺ｧ縺吶ょｮ滄圀縺ｮ繧ｯ繧ｨ繝ｪ繝ｭ繧ｰ繧貞庶髮・＠縲∝ｮ溯｡後＆繧後◆繧ｯ繧ｨ繝ｪ縺ｮ蝗樊焚縺ｨ遞ｮ鬘槭ｒ蛻・梵縺励∪縺吶・

## 荳ｻ縺ｪ讖溯・

- 笨・**繧ｯ繧ｨ繝ｪ繧ｭ繝｣繝励メ繝｣**: SQLAlchemy 縺悟ｮ溯｡後☆繧句・縺ｦ縺ｮ繧ｯ繧ｨ繝ｪ繧定ｨ倬鹸
- 笨・**N+1 蝠城｡梧､懷・**: 郢ｰ繧願ｿ斐＠螳溯｡後＆繧後ｋ繧ｯ繧ｨ繝ｪ繝代ち繝ｼ繝ｳ繧呈､懷・
- 笨・**邨ｱ險医Ξ繝昴・繝・*: 繧ｯ繧ｨ繝ｪ繧ｿ繧､繝励＃縺ｨ縺ｮ螳溯｡悟屓謨ｰ繧帝寔險・
- 笨・**隧ｳ邏ｰ繝ｭ繧ｰ**: verbose 繝｢繝ｼ繝峨〒蜈ｨ繧ｯ繧ｨ繝ｪ縺ｮ蜀・ｮｹ繧定｡ｨ遉ｺ
- 笨・**繝｢繝・Ν遒ｺ隱・*: 譁・ｭ怜・縺九ｉ繝｢繝・Ν繧ｯ繝ｩ繧ｹ繧貞叙蠕励☆繧九・繝ｫ繝代・髢｢謨ｰ

## 蝓ｺ譛ｬ逧・↑菴ｿ縺・婿

### 1. 繧､繝ｳ繝昴・繝・

```python
from repom.diagnostics.query_analyzer import QueryAnalyzer
from repom.database import get_db_session
from myapp.models import User
```

### 2. 繧ｯ繧ｨ繝ｪ縺ｮ逶｣隕・

```python
analyzer = QueryAnalyzer()

with analyzer.capture():
    # 縺薙％縺ｧ螳溯｡後＆繧後ｋ繧ｯ繧ｨ繝ｪ縺瑚ｨ倬鹸縺輔ｌ繧・
    users = session.query(User).all()
    for user in users:
        print(user.posts)  # N+1 蝠城｡後′逋ｺ逕溘☆繧句庄閭ｽ諤ｧ

# 蛻・梵邨先棡繧定｡ｨ遉ｺ
analyzer.print_report()
```

### 3. 繝ｬ繝昴・繝医・蜃ｺ蜉帑ｾ・

```
======================================================================
Query Analysis Report
======================================================================

Total Queries: 11

Query Type Breakdown:
  BEGIN: 1
  SELECT: 10

笞・・ Potential N+1 Problem Detected!
   Found 1 repeated query patterns

Repeated Query Patterns:

  Pattern (repeated 10 times):
    SELECT test_posts.id, test_posts.user_id, test_posts.title FROM test_posts WHERE test_posts.user_id = ?

======================================================================
```

## 螳溯ｷｵ萓・

### 萓・: N+1 蝠城｡後・讀懷・

```python
from repom.diagnostics.query_analyzer import QueryAnalyzer
from repom import BaseRepository
from repom.database import get_db_session
from myapp.models import Author

analyzer = QueryAnalyzer()
repo = BaseRepository(Author)

with analyzer.capture():
    # 蜈ｨ闡苓・ｒ蜿門ｾ・
    authors = repo.get_all()
    
    # 蜷・送閠・・譛ｬ縺ｫ繧｢繧ｯ繧ｻ繧ｹ・・+1 蝠城｡檎匱逕滂ｼ・
    for author in authors:
        print(f"{author.name}: {len(author.books)} books")

analyzer.print_report()
```

**蜃ｺ蜉・**
```
Total Queries: 11
Query Type Breakdown:
  SELECT: 11

笞・・ Potential N+1 Problem Detected!
   Found 1 repeated query patterns
```

### 萓・: Eager Loading 縺ｧ隗｣豎ｺ

```python
from sqlalchemy.orm import joinedload

analyzer = QueryAnalyzer()

with analyzer.capture():
    # joinedload 縺ｧ譛ｬ繧ゆｸ邱偵↓蜿門ｾ・
    authors = session.query(Author).options(joinedload(Author.books)).all()
    
    for author in authors:
        print(f"{author.name}: {len(author.books)} books")

analyzer.print_report()
```

**蜃ｺ蜉・**
```
Total Queries: 1
Query Type Breakdown:
  SELECT: 1

笨・No obvious N+1 problems detected
```

### 萓・: BaseRepository 縺ｮ default_options 繧剃ｽｿ縺・

```python
from repom import BaseRepository
from sqlalchemy.orm import joinedload

class AuthorRepository(BaseRepository[Author]):
    def __init__(self, session=None):
        super().__init__(Author, session)
        # 繝・ヵ繧ｩ繝ｫ繝医〒 books 繧・eager load
        self.default_options = [joinedload(Author.books)]

analyzer = QueryAnalyzer()
repo = AuthorRepository()

with analyzer.capture():
    authors = repo.get_all()
    for author in authors:
        print(f"{author.name}: {len(author.books)} books")

analyzer.print_report()  # N+1 蝠城｡後↑縺・
```

### 萓・: 隧ｳ邏ｰ繝ｭ繧ｰ縺ｮ陦ｨ遉ｺ

```python
analyzer = QueryAnalyzer()

with analyzer.capture():
    users = session.query(User).limit(3).all()

# verbose=True 縺ｧ蜈ｨ繧ｯ繧ｨ繝ｪ縺ｮ蜀・ｮｹ繧定｡ｨ遉ｺ
analyzer.print_report(verbose=True)
```

**蜃ｺ蜉・**
```
======================================================================
Query Analysis Report
======================================================================

Total Queries: 1

Query Type Breakdown:
  SELECT: 1

笨・No obvious N+1 problems detected

----------------------------------------------------------------------
All Captured Queries:
----------------------------------------------------------------------

1. [SELECT]
   SELECT users.id, users.name, users.email FROM users  LIMIT ? OFFSET ?

======================================================================
```

## API 繝ｪ繝輔ぃ繝ｬ繝ｳ繧ｹ

### QueryAnalyzer 繧ｯ繝ｩ繧ｹ

```python
class QueryAnalyzer:
    def __init__(self, engine: Optional[Engine] = None)
```

**繝代Λ繝｡繝ｼ繧ｿ:**
- `engine` (Optional[Engine]): 逶｣隕悶☆繧・SQLAlchemy 繧ｨ繝ｳ繧ｸ繝ｳ縲ら怐逡･譎ゅ・繝・ヵ繧ｩ繝ｫ繝医お繝ｳ繧ｸ繝ｳ繧剃ｽｿ逕ｨ

### 繝倥Ν繝代・髢｢謨ｰ

#### get_model_by_name()

```python
def get_model_by_name(model_name: str) -> Optional[Type]
```

謖・ｮ壹＠縺滓枚蟄怜・縺九ｉ繝｢繝・Ν繧ｯ繝ｩ繧ｹ繧貞叙蠕励・

**繝代Λ繝｡繝ｼ繧ｿ:**
- `model_name` (str): 繝｢繝・Ν蜷搾ｼ井ｾ・ 'User', 'Author'・・

**謌ｻ繧雁､:**
- 繝｢繝・Ν繧ｯ繝ｩ繧ｹ縲∬ｦ九▽縺九ｉ縺ｪ縺・ｴ蜷医・ None

**菴ｿ逕ｨ萓・**
```python
from repom.diagnostics.query_analyzer import get_model_by_name

User = get_model_by_name('User')
if User:
    print(f"Found model: {User.__tablename__}")
```

#### list_all_models()

```python
def list_all_models() -> List[str]
```

逋ｻ骭ｲ縺輔ｌ縺ｦ縺・ｋ蜈ｨ縺ｦ縺ｮ繝｢繝・Ν蜷阪ｒ蜿門ｾ励・

**謌ｻ繧雁､:**
- 繝｢繝・Ν蜷阪・繝ｪ繧ｹ繝茨ｼ医た繝ｼ繝域ｸ医∩・・

**菴ｿ逕ｨ萓・**
```python
from repom.diagnostics.query_analyzer import list_all_models

models = list_all_models()
print(f"Available models: {', '.join(models)}")
```

#### set_target_model()

```python
def set_target_model(self, model: Union[str, Type]) -> None
```

迚ｹ螳壹・繝｢繝・Ν繧偵ち繝ｼ繧ｲ繝・ヨ縺ｨ縺励※險ｭ螳夲ｼ亥ｰ・擂逧・↑讖溯・諡｡蠑ｵ逕ｨ・峨・

**繝代Λ繝｡繝ｼ繧ｿ:**
- `model`: 繝｢繝・Ν蜷搾ｼ域枚蟄怜・・峨∪縺溘・繝｢繝・Ν繧ｯ繝ｩ繧ｹ

**菴ｿ逕ｨ萓・**
```python
analyzer = QueryAnalyzer()
analyzer.set_target_model('User')
# 縺ｾ縺溘・
analyzer.set_target_model(User)
```

### capture() 繝｡繧ｽ繝・ラ

```python
@contextmanager
def capture(self, model: Optional[Union[str, Type]] = None)
```

繧ｯ繧ｨ繝ｪ繧偵く繝｣繝励メ繝｣縺吶ｋ繧ｳ繝ｳ繝・く繧ｹ繝医・繝阪・繧ｸ繝｣繝ｼ縲・

**繝代Λ繝｡繝ｼ繧ｿ:**
- `model` (Optional): 繧ｿ繝ｼ繧ｲ繝・ヨ繝｢繝・Ν・域枚蟄怜・縺ｾ縺溘・繧ｯ繝ｩ繧ｹ・峨ｒ謖・ｮ壼庄閭ｽ

**菴ｿ逕ｨ萓・**
```python
# 繝｢繝・Ν繧呈欠螳壹＠縺ｦ繧ｭ繝｣繝励メ繝｣
with analyzer.capture(model='User'):
    users = session.query(User).all()

# 縺ｾ縺溘・
with analyzer.capture():
    users = session.query(User).all()
```

### print_report() 繝｡繧ｽ繝・ラ

```python
def print_report(self, verbose: bool = False) -> None
```

蛻・梵邨先棡繧偵さ繝ｳ繧ｽ繝ｼ繝ｫ縺ｫ陦ｨ遉ｺ縲・

**繝代Λ繝｡繝ｼ繧ｿ:**
- `verbose` (bool): True 縺ｮ蝣ｴ蜷医∝・繧ｯ繧ｨ繝ｪ縺ｮ蜀・ｮｹ繧定｡ｨ遉ｺ

### analyze_n_plus_1() 繝｡繧ｽ繝・ラ

```python
def analyze_n_plus_1(self) -> dict
```

N+1 蝠城｡後ｒ蛻・梵縺励※邨先棡繧定ｾ樊嶌縺ｧ霑斐☆縲・

**謌ｻ繧雁､:**
```python
{
    'total_queries': int,        # 邱上け繧ｨ繝ｪ謨ｰ
    'select_queries': int,       # SELECT 繧ｯ繧ｨ繝ｪ謨ｰ
    'potential_n_plus_1': bool,  # N+1 蝠城｡後・蜿ｯ閭ｽ諤ｧ
    'repeated_queries': dict,    # 郢ｰ繧願ｿ斐＆繧後◆繧ｯ繧ｨ繝ｪ繝代ち繝ｼ繝ｳ
    'query_stats': dict          # 繧ｯ繧ｨ繝ｪ繧ｿ繧､繝励＃縺ｨ縺ｮ邨ｱ險・
}
```

### get_queries() 繝｡繧ｽ繝・ラ

```python
def get_queries(self) -> List[dict]
```

繧ｭ繝｣繝励メ繝｣縺励◆蜈ｨ繧ｯ繧ｨ繝ｪ繧貞叙蠕励・

**謌ｻ繧雁､:**
```python
[
    {
        'statement': str,   # SQL 譁・
        'type': str,        # 繧ｯ繧ｨ繝ｪ繧ｿ繧､繝・(SELECT, INSERT, 縺ｪ縺ｩ)
        'parameters': Any   # 繧ｯ繧ｨ繝ｪ繝代Λ繝｡繝ｼ繧ｿ
    },
    ...
]
```

### get_stats() 繝｡繧ｽ繝・ラ

```python
def get_stats(self) -> dict
```

繧ｯ繧ｨ繝ｪ邨ｱ險医ｒ蜿門ｾ励・

**謌ｻ繧雁､:**
```python
{
    'SELECT': 10,
    'INSERT': 2,
    'UPDATE': 1,
    ...
}
```

## 菴ｿ逕ｨ繧ｷ繝翫Μ繧ｪ

### 繝｢繝・Ν蜷阪°繧牙虚逧・↓蛻・梵

```python
from repom.diagnostics.query_analyzer import QueryAnalyzer, get_model_by_name

# 繝｢繝・Ν蜷阪′譁・ｭ怜・縺ｧ荳弱∴繧峨ｌ縺溷ｴ蜷・
model_name = 'User'
UserModel = get_model_by_name(model_name)

if UserModel:
    analyzer = QueryAnalyzer()
    with analyzer.capture(model=model_name):
        # UserModel 繧剃ｽｿ縺｣縺溘け繧ｨ繝ｪ
        users = session.query(UserModel).all()
    
    analyzer.print_report()
else:
    print(f"Model '{model_name}' not found")
```

### 蛻ｩ逕ｨ蜿ｯ閭ｽ縺ｪ繝｢繝・Ν荳隕ｧ繧堤｢ｺ隱・

```python
from repom.diagnostics.query_analyzer import list_all_models

# 蜈ｨ繝｢繝・Ν繧定｡ｨ遉ｺ
models = list_all_models()
print(f"Available models ({len(models)}):")
for model in models:
    print(f"  - {model}")
```

### 髢狗匱荳ｭ縺ｮ遒ｺ隱・

```python
# 髢狗匱荳ｭ縺ｫ繧ｳ繝ｼ繝峨・迚ｹ螳夐Κ蛻・ｒ蛻・梵
analyzer = QueryAnalyzer()

with analyzer.capture():
    result = my_function_that_queries_db()

analyzer.print_report()
```

### 繝・せ繝医〒縺ｮ菴ｿ逕ｨ

```python
def test_no_n_plus_1_in_user_list(db_test):
    """繝ｦ繝ｼ繧ｶ繝ｼ荳隕ｧ蜿門ｾ励〒 N+1 蝠城｡後′逋ｺ逕溘＠縺ｪ縺・％縺ｨ繧堤｢ｺ隱・""
    analyzer = QueryAnalyzer(engine=db_test.bind.engine)
    
    with analyzer.capture():
        users = get_user_list_with_posts()
    
    analysis = analyzer.analyze_n_plus_1()
    
    # N+1 蝠城｡後′縺ｪ縺・％縺ｨ繧偵い繧ｵ繝ｼ繝・
    assert analysis['potential_n_plus_1'] is False
    # 繧ｯ繧ｨ繝ｪ謨ｰ縺梧悄蠕・､莉･荳九〒縺ゅｋ縺薙→繧堤｢ｺ隱・
    assert analysis['total_queries'] <= 3
```

### 繝励Ο繧ｸ繧ｧ繧ｯ繝医〒縺ｮ菴ｿ逕ｨ

螟夜Κ繝励Ο繧ｸ繧ｧ繧ｯ繝茨ｼ井ｾ・ mine-py・峨°繧牙茜逕ｨ縺吶ｋ蝣ｴ蜷・

```python
# mine-py/src/mine_py/debug.py
from repom.diagnostics.query_analyzer import QueryAnalyzer
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

## 繝吶せ繝医・繝ｩ繧ｯ繝・ぅ繧ｹ

### 1. 髢狗匱荳ｭ縺ｮ邯咏ｶ夂噪縺ｪ繝√ぉ繝・け

N+1 蝠城｡後・豌励▼縺九↑縺・≧縺｡縺ｫ逋ｺ逕溘＠繧・☆縺・◆繧√∵眠縺励＞讖溯・繧貞ｮ溯｣・☆繧九◆縺ｳ縺ｫ繝√ぉ繝・け縺吶ｋ縺薙→繧呈耳螂ｨ縺励∪縺吶・

```python
# 譁ｰ讖溯・螳溯｣・ｾ・
analyzer = QueryAnalyzer()
with analyzer.capture():
    test_new_feature()
analyzer.print_report()
```

### 2. BaseRepository 縺ｮ default_options 繧呈ｴｻ逕ｨ

鬆ｻ郢√↓繧｢繧ｯ繧ｻ繧ｹ縺吶ｋ繝ｪ繝ｬ繝ｼ繧ｷ繝ｧ繝ｳ縺ｯ縲√Μ繝昴ず繝医Μ縺ｧ莠句燕螳夂ｾｩ縺励※縺翫″縺ｾ縺吶・

```python
class UserRepository(BaseRepository[User]):
    def __init__(self, session=None):
        super().__init__(User, session)
        self.default_options = [
            joinedload(User.posts),
            joinedload(User.profile)
        ]
```

### 3. 繝・せ繝医〒 N+1 繧帝亟豁｢

驥崎ｦ√↑繧ｨ繝ｳ繝峨・繧､繝ｳ繝医ｄ繧ｯ繧ｨ繝ｪ縺ｫ縺ｯ縲¨+1 蝠城｡後′逋ｺ逕溘＠縺ｪ縺・％縺ｨ繧剃ｿ晁ｨｼ縺吶ｋ繝・せ繝医ｒ霑ｽ蜉縺励∪縺吶・

```python
def test_api_endpoint_performance(client, db_test):
    analyzer = QueryAnalyzer(engine=db_test.bind.engine)
    
    with analyzer.capture():
        response = client.get('/api/users')
    
    assert response.status_code == 200
    analysis = analyzer.analyze_n_plus_1()
    assert analysis['total_queries'] <= 5  # 髢ｾ蛟､繧定ｨｭ螳・
```

## 蛻ｶ髯蝉ｺ矩・→豕ｨ諢冗せ

### 1. 讀懷・縺ｮ髯千阜

`QueryAnalyzer` 縺ｯ郢ｰ繧願ｿ斐＠繝代ち繝ｼ繝ｳ繧呈､懷・縺励∪縺吶′縲∝・縺ｦ縺ｮ N+1 蝠城｡後ｒ讀懷・縺ｧ縺阪ｋ繧上￠縺ｧ縺ｯ縺ゅｊ縺ｾ縺帙ｓ縲ゆｻ･荳九・繧医≧縺ｪ蝣ｴ蜷医・莠ｺ髢薙↓繧医ｋ蛻､譁ｭ縺悟ｿ・ｦ√〒縺・

- 諢丞峙逧・↓隍・焚繧ｯ繧ｨ繝ｪ繧貞ｮ溯｡後＠縺ｦ縺・ｋ蝣ｴ蜷・
- 繝代Λ繝｡繝ｼ繧ｿ縺檎焚縺ｪ繧区ｭ｣蠖薙↑隍・焚繧ｯ繧ｨ繝ｪ
- 隍・尅縺ｪ繧ｯ繧ｨ繝ｪ譛驕ｩ蛹悶′蠢・ｦ√↑蝣ｴ蜷・

### 2. 繝代ヵ繧ｩ繝ｼ繝槭Φ繧ｹ

`QueryAnalyzer` 縺ｯ繧､繝吶Φ繝医Μ繧ｹ繝翫・繧剃ｽｿ縺｣縺ｦ繧ｯ繧ｨ繝ｪ繧定ｨ倬鹸縺吶ｋ縺溘ａ縲√ｏ縺壹°縺ｪ繧ｪ繝ｼ繝舌・繝倥ャ繝峨′縺ゅｊ縺ｾ縺吶よ悽逡ｪ迺ｰ蠅・〒縺ｯ菴ｿ逕ｨ縺励↑縺・〒縺上□縺輔＞縲・

### 3. 繝・せ繝育腸蠅・〒縺ｮ菴ｿ逕ｨ

繝・せ繝医〒菴ｿ逕ｨ縺吶ｋ蝣ｴ蜷医～db_test` 繝輔ぅ繧ｯ繧ｹ繝√Ε縺ｮ繧ｨ繝ｳ繧ｸ繝ｳ繧呈・遉ｺ逧・↓貂｡縺吝ｿ・ｦ√′縺ゅｊ縺ｾ縺・

```python
# 笨・豁｣縺励＞
analyzer = QueryAnalyzer(engine=db_test.bind.engine)

# 笶・隱､繧奇ｼ医ョ繝輔か繝ｫ繝医お繝ｳ繧ｸ繝ｳ繧剃ｽｿ縺｣縺ｦ縺励∪縺・ｼ・
analyzer = QueryAnalyzer()
```

## 縺ｾ縺ｨ繧・

`QueryAnalyzer` 縺ｯ N+1 蝠城｡後ｒ譌ｩ譛溘↓逋ｺ隕九＠縲√ヱ繝輔か繝ｼ繝槭Φ繧ｹ蝠城｡後ｒ譛ｪ辟ｶ縺ｫ髦ｲ縺舌◆繧√・蠑ｷ蜉帙↑繝・・繝ｫ縺ｧ縺吶る幕逋ｺ繝励Ο繧ｻ繧ｹ縺ｫ邨・∩霎ｼ繧縺薙→縺ｧ縲√ョ繝ｼ繧ｿ繝吶・繧ｹ繧ｯ繧ｨ繝ｪ縺ｮ譛驕ｩ蛹悶ｒ邯咏ｶ夂噪縺ｫ陦後≧縺薙→縺後〒縺阪∪縺吶・

## 髢｢騾｣繝峨く繝･繝｡繝ｳ繝・

- [BaseRepository Guide](../repository/base_repository_guide.md) - 繝ｪ繝昴ず繝医Μ縺ｮ蝓ｺ譛ｬ逧・↑菴ｿ縺・婿
- [Repository Advanced Guide](../repository/repository_advanced_guide.md) - Eager Loading 縺ｮ隧ｳ邏ｰ
- [Testing Guide](../testing/testing_guide.md) - 繝・せ繝医〒縺ｮ菴ｿ逕ｨ譁ｹ豕・
