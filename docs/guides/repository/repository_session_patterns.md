# Repository 繧ｻ繝・す繝ｧ繝ｳ邂｡逅・ヱ繧ｿ繝ｼ繝ｳ繧ｬ繧､繝・

**逶ｮ逧・*: BaseRepository 縺ｧ縺ｮ繧ｻ繝・す繝ｧ繝ｳ邂｡逅・・莉慕ｵ・∩縺ｨ謗ｨ螂ｨ繝代ち繝ｼ繝ｳ繧堤炊隗｣縺吶ｋ

**蟇ｾ雎｡隱ｭ閠・*: repom 繧剃ｽｿ縺｣縺ｦ繝ｪ繝昴ず繝医Μ繝代ち繝ｼ繝ｳ繧貞ｮ溯｣・☆繧矩幕逋ｺ閠・・AI 繧ｨ繝ｼ繧ｸ繧ｧ繝ｳ繝・

---

## 答 逶ｮ谺｡

1. [讎りｦ‐(#讎りｦ・
2. [BaseRepository 縺ｮ繧ｻ繝・す繝ｧ繝ｳ邂｡逅・・莉慕ｵ・∩](#baserepository-縺ｮ繧ｻ繝・す繝ｧ繝ｳ邂｡逅・・莉慕ｵ・∩)
3. [謗ｨ螂ｨ繝代ち繝ｼ繝ｳ](#謗ｨ螂ｨ繝代ち繝ｼ繝ｳ)
4. [螳溯｣・ｾ犠(#螳溯｣・ｾ・
5. [繧医￥縺ゅｋ髢馴＆縺Ь(#繧医￥縺ゅｋ髢馴＆縺・
6. [繝代ち繝ｼ繝ｳ驕ｸ謚槭ぎ繧､繝云(#繝代ち繝ｼ繝ｳ驕ｸ謚槭ぎ繧､繝・

---

## 讎りｦ・

`BaseRepository` 縺ｯ **`session=None` 繧定ｨｱ螳ｹ** 縺励√そ繝・す繝ｧ繝ｳ縺梧署萓帙＆繧後※縺・↑縺・ｴ蜷医・閾ｪ蜍慕噪縺ｫ `get_db_session()` 繧剃ｽｿ逕ｨ縺励∪縺吶ゅ％繧後↓繧医ｊ縲√す繝ｳ繝励Ν縺ｪ菴ｿ縺・婿縺九ｉ鬮伜ｺｦ縺ｪ繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ蛻ｶ蠕｡縺ｾ縺ｧ縲∵沐霆溘↑螳溯｣・′蜿ｯ閭ｽ縺ｧ縺吶・

**驥崎ｦ・*: Repository 縺ｮ `__init__` 縺ｧ `session is None` 繧偵メ繧ｧ繝・け縺励※ `ValueError` 繧・raise 縺吶ｋ蠢・ｦ√・ **縺ゅｊ縺ｾ縺帙ｓ**縲・aseRepository 縺瑚・蜍慕噪縺ｫ蜃ｦ逅・＠縺ｾ縺吶・

---

## BaseRepository 縺ｮ繧ｻ繝・す繝ｧ繝ｳ邂｡逅・・莉慕ｵ・∩

### 蜀・Κ螳溯｣・

```python
class BaseRepository(Generic[T]):
    def __init__(self, model: Type[T], session: Optional[Session] = None):
        self.model = model
        self.session = session  # None 縺ｧ繧・OK

    def get_by_id(self, id: int) -> Optional[T]:
        # session 縺・None 縺ｮ蝣ｴ蜷医“et_db_session() 繧剃ｽｿ逕ｨ
        if self.session is None:
            with get_db_session() as session:
                return session.query(self.model).filter_by(id=id).first()
        else:
            # 貂｡縺輔ｌ縺溘そ繝・す繝ｧ繝ｳ繧剃ｽｿ逕ｨ
            return self.session.query(self.model).filter_by(id=id).first()
```

**繝昴う繝ｳ繝・*:
- `session=None` 縺ｧ繧､繝ｳ繧ｹ繧ｿ繝ｳ繧ｹ蛹門庄閭ｽ
- 蜷・Γ繧ｽ繝・ラ縺ｧ `self.session is None` 繧偵メ繧ｧ繝・け
- None 縺ｮ蝣ｴ蜷医・ `get_db_session()` 縺ｧ閾ｪ蜍輔そ繝・す繝ｧ繝ｳ菴懈・
- 謠蝉ｾ帙＆繧後※縺・ｋ蝣ｴ蜷医・縺昴ｌ繧剃ｽｿ逕ｨ

---

## 謗ｨ螂ｨ繝代ち繝ｼ繝ｳ

### 繝代ち繝ｼ繝ｳ 1: 繧ｻ繝・す繝ｧ繝ｳ縺ｪ縺暦ｼ域怙繧ゅす繝ｳ繝励Ν・・

**迚ｹ蠕ｴ**:
- 笨・繧ｳ繝ｼ繝峨′譛繧ゅす繝ｳ繝励Ν
- 笨・蜊倡ｴ斐↑ CRUD 謫堺ｽ懊↓譛驕ｩ
- 笶・繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ蛻ｶ蠕｡縺ｪ縺暦ｼ亥推謫堺ｽ懊′蛟句挨繧ｳ繝溘ャ繝茨ｼ・
- 笶・隍・焚謫堺ｽ懊ｒ繧｢繝医Α繝・け縺ｫ縺ｧ縺阪↑縺・

```python
from repom import BaseRepository
from your_project.models import VoiceScript

class VoiceScriptRepository(BaseRepository[VoiceScript]):
    pass

# 菴ｿ縺・婿
repo = VoiceScriptRepository()
script = repo.get_by_id(1)
scripts = repo.get_all()
```

**驕ｩ逕ｨ蝣ｴ髱｢**:
- 隱ｭ縺ｿ蜿悶ｊ蟆ら畑縺ｮ謫堺ｽ・
- 蜊倅ｸ繝ｬ繧ｳ繝ｼ繝峨・菴懈・繝ｻ譖ｴ譁ｰ繝ｻ蜑企勁
- 繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ蛻ｶ蠕｡縺御ｸ崎ｦ√↑蝣ｴ蜷・

---

### 繝代ち繝ｼ繝ｳ 2: 譏守､ｺ逧・ヨ繝ｩ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ・域耳螂ｨ・・

**迚ｹ蠕ｴ**:
- 笨・隍・焚謫堺ｽ懊ｒ繧｢繝医Α繝・け縺ｫ螳溯｡悟庄閭ｽ
- 笨・繧ｨ繝ｩ繝ｼ譎ゅ・閾ｪ蜍輔Ο繝ｼ繝ｫ繝舌ャ繧ｯ
- 笨・繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ蛻ｶ蠕｡縺梧・遒ｺ
- 笞・・繧・ｄ蜀鈴聞・・ith 譁・′蠢・ｦ・ｼ・

**驥崎ｦ√↑蜍穂ｽ・*:
- 螟夜Κ繧ｻ繝・す繝ｧ繝ｳ繧呈ｸ｡縺励◆蝣ｴ蜷医ヽepository 縺ｮ `save()` / `saves()` / `remove()` 縺ｯ `commit()` 繧貞ｮ溯｡後＠縺ｾ縺帙ｓ
- 莉｣繧上ｊ縺ｫ `flush()` 縺ｮ縺ｿ縺悟ｮ溯｡後＆繧後∝､画峩縺ｯ繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ蜀・〒菫晉蕗縺輔ｌ縺ｾ縺・
- `commit()` 縺ｯ `with` 繝悶Ο繝・け邨ゆｺ・凾・医∪縺溘・譏守､ｺ逧・↑蜻ｼ縺ｳ蜃ｺ縺暦ｼ峨∪縺ｧ螳溯｡後＆繧後∪縺帙ｓ

```python
from repom.database import _db_manager
from your_project.models import VoiceScript

class VoiceScriptRepository(BaseRepository[VoiceScript]):
    pass

# 菴ｿ縺・婿
with _db_manager.get_sync_transaction() as session:
    repo = VoiceScriptRepository(session)
    script = repo.get_by_id(1)
    script.title = "譖ｴ譁ｰ"
    
    # save() 縺ｯ flush 縺ｮ縺ｿ螳溯｡鯉ｼ・ommit 縺励↑縺・ｼ・
    repo.save(script)
    
    # 霑ｽ蜉縺ｮ謫堺ｽ懊ｂ蜷後§繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ蜀・
    script2 = repo.get_by_id(2)
    repo.remove(script2)  # 縺薙ｌ繧・flush 縺ｮ縺ｿ
    
    # with 繝悶Ο繝・け邨ゆｺ・凾縺ｫ蜈ｨ縺ｦ縺ｮ螟画峩縺・commit 縺輔ｌ繧・
```

**驕ｩ逕ｨ蝣ｴ髱｢**:
- 隍・焚繝ｬ繧ｳ繝ｼ繝峨・菴懈・繝ｻ譖ｴ譁ｰ繝ｻ蜑企勁
- 隍・焚繝・・繝悶Ν縺ｫ縺ｾ縺溘′繧区桃菴・
- 繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ縺ｮ荳雋ｫ諤ｧ縺碁㍾隕√↑蝣ｴ蜷・

---

### 繝代ち繝ｼ繝ｳ 3: FastAPI Depends 繝代ち繝ｼ繝ｳ

**迚ｹ蠕ｴ**:
- 笨・FastAPI 縺ｮ萓晏ｭ俶ｧ豕ｨ蜈･繧呈ｴｻ逕ｨ
- 笨・繧ｨ繝ｳ繝峨・繧､繝ｳ繝亥腰菴阪〒繧ｻ繝・す繝ｧ繝ｳ邂｡逅・
- 笨・繝・せ繝医＠繧・☆縺・
- 笞・・FastAPI 蟆ら畑

**驥崎ｦ・*: `get_db_session()` / `get_db_transaction()` 縺ｯ FastAPI Depends 蟆ら畑縺ｧ縺吶・
with 譁・〒菴ｿ逕ｨ縺吶ｋ縺薙→縺ｯ**縺ｧ縺阪∪縺帙ｓ**縲Ｘith 譁・ｒ菴ｿ縺・ｴ蜷医・ `_db_manager.get_sync_session()` 繧剃ｽｿ逕ｨ縺励※縺上□縺輔＞縲・

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from repom.database import get_db_session
from your_project.models import VoiceScript

router = APIRouter()

class VoiceScriptRepository(BaseRepository[VoiceScript]):
    pass

@router.get("/scripts/{script_id}")
def get_script(
    script_id: int,
    session: Session = Depends(get_db_session)
):
    repo = VoiceScriptRepository(session)
    return repo.get_by_id(script_id)
```

**驕ｩ逕ｨ蝣ｴ髱｢**:
- FastAPI 繧｢繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ
- RESTful API 繧ｨ繝ｳ繝峨・繧､繝ｳ繝・
- 繝・せ繧ｿ繝薙Μ繝・ぅ縺碁㍾隕√↑蝣ｴ蜷・

---

## 螳溯｣・ｾ・

### 萓・1: 繧ｷ繝ｳ繝励Ν縺ｪ Repository・医そ繝・す繝ｧ繝ｳ縺ｪ縺暦ｼ・

```python
from repom import BaseRepository
from your_project.models import User

class UserRepository(BaseRepository[User]):
    """繧ｻ繝・す繝ｧ繝ｳ邂｡逅・・ BaseRepository 縺ｫ莉ｻ縺帙ｋ"""
    pass

# 菴ｿ縺・婿
repo = UserRepository()

# 隱ｭ縺ｿ蜿悶ｊ
user = repo.get_by_id(1)
users = repo.get_by("email", "test@example.com")

# 菴懈・
new_user = User(name="螟ｪ驛・, email="taro@example.com")
saved_user = repo.save(new_user)
```

---

### 萓・2: 繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ蛻ｶ蠕｡縺悟ｿ・ｦ√↑ Repository

```python
from repom import BaseRepository
from repom.database import get_db_transaction
from your_project.models import Order, OrderItem

class OrderRepository(BaseRepository[Order]):
    pass

class OrderItemRepository(BaseRepository[OrderItem]):
    pass

# 菴ｿ縺・婿・夊､・焚繝・・繝悶Ν縺ｮ謫堺ｽ懊ｒ 1 繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ縺ｧ
def create_order_with_items(order_data: dict, items_data: list[dict]):
    from repom.database import _db_manager
    
    with _db_manager.get_sync_transaction() as session:
        order_repo = OrderRepository(session)
        item_repo = OrderItemRepository(session)
        
        # 豕ｨ譁・ｽ懈・
        order = order_repo.dict_save(order_data)
        
        # 豕ｨ譁・・邏ｰ菴懈・
        for item_data in items_data:
            item_data["order_id"] = order.id
            item_repo.dict_save(item_data)
        
        # with 繝悶Ο繝・け邨ゆｺ・凾縺ｫ閾ｪ蜍輔さ繝溘ャ繝・
        # 繧ｨ繝ｩ繝ｼ逋ｺ逕滓凾縺ｯ閾ｪ蜍輔Ο繝ｼ繝ｫ繝舌ャ繧ｯ
```

---

### 萓・3: FastAPI 縺ｧ縺ｮ Repository 菴ｿ逕ｨ

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from repom.database import get_db_session
from your_project.models import Task
from your_project.schemas import TaskCreate, TaskUpdate

router = APIRouter()

class TaskRepository(BaseRepository[Task]):
    pass

@router.post("/tasks")
def create_task(
    task_data: TaskCreate,
    session: Session = Depends(get_db_session)
):
    repo = TaskRepository(session)
    task = repo.dict_save(task_data.model_dump())
    session.commit()  # 譏守､ｺ逧・↓繧ｳ繝溘ャ繝・
    return task

@router.put("/tasks/{task_id}")
def update_task(
    task_id: int,
    task_data: TaskUpdate,
    session: Session = Depends(get_db_session)
):
    repo = TaskRepository(session)
    task = repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 譖ｴ譁ｰ
    for key, value in task_data.model_dump(exclude_unset=True).items():
        setattr(task, key, value)
    
    session.commit()
    return task
```

---

## 繧医￥縺ゅｋ髢馴＆縺・

### 笶・髢馴＆縺・1: session=None 縺ｧ ValueError 繧・raise

```python
# 縺薙ｌ縺ｯ荳崎ｦ・ｼ・
class VoiceScriptRepository(BaseRepository[VoiceScript]):
    def __init__(self, session=None):
        if session is None:
            raise ValueError("session is required")  # 笶・荳崎ｦ・
        super().__init__(VoiceScript, session)
```

**逅・罰**: BaseRepository 縺・`session=None` 繧定・蜍慕噪縺ｫ蜃ｦ逅・＠縺ｾ縺吶ゅお繝ｩ繝ｼ繧・raise 縺吶ｋ縺ｨ縲√す繝ｳ繝励Ν縺ｪ菴ｿ縺・婿・医ヱ繧ｿ繝ｼ繝ｳ 1・峨′縺ｧ縺阪↑縺上↑繧翫∪縺吶・

---

### 笶・髢馴＆縺・2: __init__ 縺ｧ get_db_session() 繧貞他縺ｶ

```python
# 縺薙ｌ縺ｯ驕ｿ縺代ｋ・・
class VoiceScriptRepository(BaseRepository[VoiceScript]):
    def __init__(self, session=None):
        if session is None:
            session = get_db_session()  # 笶・繧ｸ繧ｧ繝阪Ξ繝ｼ繧ｿ縺ｪ縺ｮ縺ｧ譛溷ｾ・壹ｊ蜍輔°縺ｪ縺・
        super().__init__(VoiceScript, session)
```

**逅・罰**: `get_db_session()` 縺ｯ繧ｸ繧ｧ繝阪Ξ繝ｼ繧ｿ縺ｪ縺ｮ縺ｧ縲～next()` 繧・`with` 譁・〒菴ｿ縺・ｿ・ｦ√′縺ゅｊ縺ｾ縺吶・aseRepository 縺ｫ莉ｻ縺帙ｋ縺ｮ縺梧ｭ｣隗｣縺ｧ縺吶・

---

### 笶・髢馴＆縺・3: 繝代ち繝ｼ繝ｳ 1 縺ｧ隍・焚謫堺ｽ懊ｒ螳溯｡・

```python
# 縺薙ｌ縺ｯ蜊ｱ髯ｺ・・
repo = VoiceScriptRepository()  # 繧ｻ繝・す繝ｧ繝ｳ縺ｪ縺・

# 蜷・桃菴懊′蛟句挨縺ｮ繧ｻ繝・す繝ｧ繝ｳ縺ｧ螳溯｡後＆繧後ｋ
user = repo.get_by_id(1)       # 繧ｻ繝・す繝ｧ繝ｳ 1
order = repo.get_by_id(2)      # 繧ｻ繝・す繝ｧ繝ｳ 2
order.user_id = user.id        # 笶・order 縺ｯ蛻･繧ｻ繝・す繝ｧ繝ｳ縺ｮ繧ｪ繝悶ず繧ｧ繧ｯ繝・
repo.save(order)               # 繧ｨ繝ｩ繝ｼ: DetachedInstanceError
```

**隗｣豎ｺ遲・*: 隍・焚謫堺ｽ懊・ `_db_manager.get_sync_transaction()` 縺ｧ繝ｩ繝・・縺吶ｋ・医ヱ繧ｿ繝ｼ繝ｳ 2・・

```python
# 笨・豁｣縺励＞
from repom.database import _db_manager

with _db_manager.get_sync_transaction() as session:
    repo = VoiceScriptRepository(session)
    user = repo.get_by_id(1)
    order = repo.get_by_id(2)
    order.user_id = user.id
    repo.save(order)  # OK: 蜷後§繧ｻ繝・す繝ｧ繝ｳ
```

---

### 笶・髢馴＆縺・4: get_db_session() 繧・with 譁・〒菴ｿ縺翫≧縺ｨ縺吶ｋ

```python
# 笶・縺薙ｌ縺ｯ蜍穂ｽ懊＠縺ｾ縺帙ｓ・・
with get_db_session() as session:  # TypeError: 'generator' object does not support the context manager protocol
    repo = TaskRepository(session)
    return repo.dict_save(data)
```

**逅・罰**: `get_db_session()` / `get_db_transaction()` 縺ｯ FastAPI Depends 蟆ら畑縺ｮ generator 髢｢謨ｰ縺ｧ縺吶Ｘith 譁・〒縺ｯ菴ｿ逕ｨ縺ｧ縺阪∪縺帙ｓ縲・

**豁｣縺励＞譁ｹ豕・*:
```python
# 笨・with 譁・ｒ菴ｿ縺・◆縺・ｴ蜷・
from repom.database import _db_manager

with _db_manager.get_sync_session() as session:
    repo = TaskRepository(session)
    return repo.dict_save(data)

# 笨・FastAPI 縺ｧ縺ｯ Depends 繧剃ｽｿ縺・
from fastapi import Depends
from repom.database import get_db_session

@router.post("/tasks")
def create_task(
    task_data: TaskCreate,
    session: Session = Depends(get_db_session)
):
    repo = TaskRepository(session)
    task = repo.dict_save(task_data.model_dump())
    session.commit()
    return task
```

**謗ｨ螂ｨ**:
```python
# 笨・FastAPI 縺ｧ縺ｯ Depends 繧剃ｽｿ縺・
@router.post("/tasks")
def create_task(
    task_data: TaskCreate,
    session: Session = Depends(get_db_session)
):
    repo = TaskRepository(session)
    task = repo.dict_save(task_data.model_dump())
    session.commit()
    return task
```

---

## 繝代ち繝ｼ繝ｳ驕ｸ謚槭ぎ繧､繝・

| 迥ｶ豕・| 謗ｨ螂ｨ繝代ち繝ｼ繝ｳ | 逅・罰 |
|------|-------------|------|
| 蜊倡ｴ斐↑隱ｭ縺ｿ蜿悶ｊ | 繝代ち繝ｼ繝ｳ 1・医そ繝・す繝ｧ繝ｳ縺ｪ縺暦ｼ・| 譛繧ゅす繝ｳ繝励Ν |
| 蜊倅ｸ繝ｬ繧ｳ繝ｼ繝峨・菴懈・繝ｻ譖ｴ譁ｰ | 繝代ち繝ｼ繝ｳ 1・医そ繝・す繝ｧ繝ｳ縺ｪ縺暦ｼ・| 繧ｳ繝ｼ繝峨′邁｡貎・|
| 隍・焚繝ｬ繧ｳ繝ｼ繝峨・謫堺ｽ・| 繝代ち繝ｼ繝ｳ 2・域・遉ｺ逧・ヨ繝ｩ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ・・| 繧｢繝医Α繝・け諤ｧ縺御ｿ晁ｨｼ縺輔ｌ繧・|
| 隍・焚繝・・繝悶Ν縺ｮ謫堺ｽ・| 繝代ち繝ｼ繝ｳ 2・域・遉ｺ逧・ヨ繝ｩ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ・・| 繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ縺ｮ荳雋ｫ諤ｧ |
| FastAPI 繧ｨ繝ｳ繝峨・繧､繝ｳ繝・| 繝代ち繝ｼ繝ｳ 3・・epends・・| FastAPI 縺ｮ諷｣鄙偵↓蠕薙≧ |
| CLI 繧ｹ繧ｯ繝ｪ繝励ヨ | 繝代ち繝ｼ繝ｳ 2・域・遉ｺ逧・ヨ繝ｩ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ・・| 繧ｨ繝ｩ繝ｼ繝上Φ繝峨Μ繝ｳ繧ｰ縺梧・遒ｺ |
| 繝舌ャ繧ｯ繧ｰ繝ｩ繧ｦ繝ｳ繝峨ず繝ｧ繝・| 繝代ち繝ｼ繝ｳ 2・域・遉ｺ逧・ヨ繝ｩ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ・・| 繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ蛻ｶ蠕｡縺碁㍾隕・|

---

## 繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ邂｡逅・・隧ｳ邏ｰ

### 蜀・Κ繧ｻ繝・す繝ｧ繝ｳ vs 螟夜Κ繧ｻ繝・す繝ｧ繝ｳ

repom 縺ｮ Repository 縺ｯ貂｡縺輔ｌ縺溘そ繝・す繝ｧ繝ｳ縺ｮ遞ｮ鬘槭ｒ閾ｪ蜍募愛螳壹＠縲・←蛻・↑蜍穂ｽ懊ｒ驕ｸ謚槭＠縺ｾ縺呻ｼ・

| 繧ｻ繝・す繝ｧ繝ｳ繧ｿ繧､繝・| 蛻､螳壽婿豕・| `save()` 縺ｮ蜍穂ｽ・| `commit()` 縺ｮ雋ｬ莉ｻ |
|----------------|---------|---------------|-----------------|
| **蜀・Κ繧ｻ繝・す繝ｧ繝ｳ** | `session=None` 縺ｧ蛻晄悄蛹・| `flush()` + `commit()` | Repository |
| **螟夜Κ繧ｻ繝・す繝ｧ繝ｳ** | 譏守､ｺ逧・↓貂｡縺輔ｌ繧・| `flush()` 縺ｮ縺ｿ | 蜻ｼ縺ｳ蜃ｺ縺怜・ |

### 蛻､螳壹Ο繧ｸ繝・け

```python
# BaseRepository / AsyncBaseRepository 蜀・Κ縺ｮ蛻､螳・
using_internal_session = (
    self._session_override is None and 
    self._scoped_session is session
)

if using_internal_session:
    session.commit()  # 蜀・Κ繧ｻ繝・す繝ｧ繝ｳ: Repository 縺・commit
else:
    session.flush()   # 螟夜Κ繧ｻ繝・す繝ｧ繝ｳ: 蜻ｼ縺ｳ蜃ｺ縺怜・縺・commit
```

### 螟夜Κ繧ｻ繝・す繝ｧ繝ｳ縺ｮ蛻ｩ轤ｹ

1. **繧｢繝医Α繝・け諤ｧ**: 隍・焚縺ｮ Repository 謫堺ｽ懊ｒ 1 繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ縺ｫ縺ｾ縺ｨ繧√ｉ繧後ｋ
2. **繝ｭ繝ｼ繝ｫ繝舌ャ繧ｯ蛻ｶ蠕｡**: 繧ｨ繝ｩ繝ｼ譎ゅ・ rollback 繧剃ｸ邂・園縺ｧ邂｡逅・
3. **繝代ヵ繧ｩ繝ｼ繝槭Φ繧ｹ**: commit 繧呈怙蠕後↓縺ｾ縺ｨ繧√ｋ縺薙→縺ｧ DB 繧｢繧ｯ繧ｻ繧ｹ繧貞炎貂・

### 螳溯｣・ｾ・

```python
# 隍・焚 Repository 繧・1 繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ縺ｧ菴ｿ逕ｨ
from repom.database import _db_manager

with _db_manager.get_sync_transaction() as session:
    user_repo = UserRepository(session)
    order_repo = OrderRepository(session)
    
    # 繝ｦ繝ｼ繧ｶ繝ｼ菴懈・・・lush 縺ｮ縺ｿ・・
    user = user_repo.save(User(name="螟ｪ驛・))
    
    # 豕ｨ譁・ｽ懈・・・lush 縺ｮ縺ｿ・・
    order = order_repo.save(Order(user_id=user.id, total=1000))
    
    # 蜈ｨ縺ｦ縺ｾ縺ｨ繧√※ commit・・ith 繝悶Ο繝・け邨ゆｺ・凾・・
```

**豕ｨ諢丈ｺ矩・*:
- 螟夜Κ繧ｻ繝・す繝ｧ繝ｳ縺ｧ縺ｯ `save()` 縺・`flush()` 縺ｮ縺ｿ螳溯｡後＠縲～refresh()` 縺ｯ螳溯｡後＠縺ｾ縺帙ｓ
  * **蜷梧悄迚茨ｼ・aseRepository・・*: 蜀・Κ繧ｻ繝・す繝ｧ繝ｳ菴ｿ逕ｨ譎ゅ・縺ｿ `refresh()` 繧貞ｮ溯｡・
  * **髱槫酔譛溽沿・・syncBaseRepository・・*: 蜀・Κ繧ｻ繝・す繝ｧ繝ｳ菴ｿ逕ｨ譎ゅ・縺ｿ `refresh()` 繧貞ｮ溯｡・
- AutoDateTime 縺ｪ縺ｩ縺ｮ DB 閾ｪ蜍戊ｨｭ螳壼､繧貞叙蠕励☆繧九↓縺ｯ縲∵・遉ｺ逧・↑ `refresh()` 縺悟ｿ・ｦ√〒縺・
  ```python
  # 螟夜Κ繧ｻ繝・す繝ｧ繝ｳ菴ｿ逕ｨ譎・
  with _db_manager.get_sync_transaction() as session:
      repo = UserRepository(session)
      user = repo.save(User(name="螟ｪ驛・))
      
      # created_at 縺ｯ縺ｾ縺 None・・lush 縺ｮ縺ｿ螳溯｡鯉ｼ・
      assert user.created_at is None
      
      # 譏守､ｺ逧・↓ refresh 縺吶ｌ縺ｰ蜿門ｾ怜庄閭ｽ
      session.refresh(user)
      assert user.created_at is not None
  ```
- 繧ｨ繝ｩ繝ｼ逋ｺ逕滓凾縲∝､夜Κ繧ｻ繝・す繝ｧ繝ｳ縺ｧ縺ｯ Repository 縺・rollback 繧貞ｮ溯｡後○縺壹∝他縺ｳ蜃ｺ縺怜・縺ｫ蟋斐・縺ｾ縺・
- 蜀・Κ繧ｻ繝・す繝ｧ繝ｳ菴ｿ逕ｨ譎ゅ・蜍穂ｽ懊・螟画峩縺ｪ縺暦ｼ亥ｾ梧婿莠呈鋤諤ｧ繧堤ｶｭ謖・ｼ・

---

## FastAPI 邨ｱ蜷医ヱ繧ｿ繝ｼ繝ｳ

### FastAPI Depends 縺ｮ菴ｿ縺・婿

FastAPI 縺ｮ萓晏ｭ俶ｧ豕ｨ蜈･繧ｷ繧ｹ繝・Β縺ｨ邨ｱ蜷医☆繧句ｴ蜷医～get_async_db_session()` 繧剃ｽｿ逕ｨ縺励∪縺呻ｼ・

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from repom.database import get_async_db_session
from your_project.models import Article
from your_project.schemas import ArticleResponse, ArticleCreate

router = APIRouter()

@router.get("/articles/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: int,
    session: AsyncSession = Depends(get_async_db_session)
):
    """險倅ｺ九ｒ蜿門ｾ・""
    result = await session.execute(
        select(Article).where(Article.id == article_id)
    )
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article.to_dict()

@router.post("/articles", response_model=ArticleResponse)
async def create_article(
    data: ArticleCreate,
    session: AsyncSession = Depends(get_async_db_session)
):
    """險倅ｺ九ｒ菴懈・"""
    article = Article(**data.dict())
    session.add(article)
    await session.flush()  # ID 繧貞叙蠕・
    return article.to_dict()
    # 閾ｪ蜍輔〒 commit 縺輔ｌ繧・
```

### FastAPI Users 繝代ち繝ｼ繝ｳ

FastAPI Users 縺ｯ `AsyncGenerator[AsyncSession, None]` 蝙九・萓晏ｭ倬未謨ｰ繧定ｦ∵ｱゅ＠縺ｾ縺呻ｼ・

```python
from fastapi import Depends, FastAPI
from fastapi_users import FastAPIUsers
from fastapi_users.db import SQLAlchemyUserDatabase
from repom.database import get_async_db_session
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

app = FastAPI()

# FastAPI Users 縺ｮ縺溘ａ縺ｮ萓晏ｭ倬未謨ｰ
async def get_user_db(
    session: AsyncSession = Depends(get_async_db_session)
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User)

# FastAPI Users 縺ｮ蛻晄悄蛹・
fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)

# 繝ｫ繝ｼ繧ｿ繝ｼ逋ｻ骭ｲ
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
```

### 螳溯｣・・莉慕ｵ・∩縺ｨ菴ｿ縺・・縺・

repom 縺ｫ縺ｯ **2遞ｮ鬘槭・繧ｻ繝・す繝ｧ繝ｳ蜿門ｾ玲婿豕・* 縺後≠繧翫∪縺呻ｼ・

#### 1. FastAPI Depends 蟆ら畑髢｢謨ｰ・・enerator・・

```python
def get_db_session():
    """FastAPI Depends 蟆ら畑 - with 譁・〒縺ｯ菴ｿ縺医∪縺帙ｓ"""
    session = _db_manager.get_sync_session()
    try:
        yield session
    finally:
        session.close()

def get_db_transaction():
    """FastAPI Depends 蟆ら畑 - with 譁・〒縺ｯ菴ｿ縺医∪縺帙ｓ"""
    session = _db_manager.get_sync_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

**菴ｿ縺・婿**: FastAPI 縺ｮ `Depends()` 縺ｧ縺ｮ縺ｿ菴ｿ逕ｨ
```python
from fastapi import Depends
from repom.database import get_db_session

@app.post("/items")
def create_item(
    data: ItemCreate,
    session: Session = Depends(get_db_session)  # 笨・OK
):
    item = Item(**data.dict())
    session.add(item)
    session.commit()
    return item
```

#### 2. DatabaseManager 縺ｮ繝｡繧ｽ繝・ラ・・ontext manager・・

```python
from repom.database import _db_manager

# with 譁・〒菴ｿ逕ｨ縺吶ｋ蝣ｴ蜷医・縺薙■繧・
with _db_manager.get_sync_session() as session:  # 笨・OK
    session.query(Model).all()

with _db_manager.get_sync_transaction() as session:  # 笨・OK
    session.add(item)
    # 閾ｪ蜍輔さ繝溘ャ繝・
```

**驥崎ｦ√・繧､繝ｳ繝・*:
- 笶・`get_db_session()` 繧・with 譁・〒菴ｿ逕ｨ縺吶ｋ縺薙→縺ｯ**縺ｧ縺阪∪縺帙ｓ**
- 笨・with 譁・ｒ菴ｿ縺・◆縺・ｴ蜷医・ `_db_manager.get_sync_session()` 繧剃ｽｿ逕ｨ
- 笨・FastAPI 縺ｧ縺ｯ `Depends(get_db_session)` 繧剃ｽｿ逕ｨ
- 笨・CLI 繧ｹ繧ｯ繝ｪ繝励ヨ縺ｧ縺ｯ `_db_manager.get_sync_transaction()` 繧剃ｽｿ逕ｨ

---

## 繝医Λ繝悶Ν繧ｷ繝･繝ｼ繝・ぅ繝ｳ繧ｰ

### TypeError: 'generator' object does not support the context manager protocol

**蜴溷屏**: `get_db_session()` / `get_db_transaction()` 繧・with 譁・〒菴ｿ縺翫≧縺ｨ縺励※縺・∪縺吶・

**蝠城｡後・繧ｳ繝ｼ繝我ｾ・*:
```python
# 笶・縺薙ｌ縺ｯ蜍穂ｽ懊＠縺ｾ縺帙ｓ
from repom.database import get_db_session

with get_db_session() as session:
    # TypeError: 'generator' object does not support the context manager protocol
    session.execute(...)
```

**隗｣豎ｺ譁ｹ豕・*:

**譁ｹ豕・1: FastAPI 縺ｧ縺ｯ Depends 繧剃ｽｿ縺・*・域耳螂ｨ・・
```python
# 笨・FastAPI 縺ｮ蝣ｴ蜷・
from fastapi import Depends
from sqlalchemy.orm import Session
from repom.database import get_db_session

@app.post("/items")
def create_item(
    data: ItemCreate,
    session: Session = Depends(get_db_session)  # 笨・OK
):
    session.execute(...)
    session.commit()
```

**譁ｹ豕・2: with 譁・ｒ菴ｿ縺・ｴ蜷医・ DatabaseManager 繧剃ｽｿ縺・*:
```python
# 笨・CLI 繧・せ繧ｯ繝ｪ繝励ヨ縺ｮ蝣ｴ蜷・
from repom.database import _db_manager

with _db_manager.get_sync_session() as session:  # 笨・OK
    session.execute(...)

with _db_manager.get_sync_transaction() as session:  # 笨・OK・郁・蜍輔さ繝溘ャ繝茨ｼ・
    session.execute(...)
```

**謚陦鍋噪縺ｪ閭梧勹**:
- `get_db_session()` 縺ｯ邏皮ｲ九↑ generator 髢｢謨ｰ・・astAPI Depends 蟆ら畑・・
- generator 縺ｯ context manager 繝励Ο繝医さ繝ｫ繧偵し繝昴・繝医＠縺ｦ縺・↑縺・
- with 譁・ｒ菴ｿ縺・ｴ蜷医・ `_db_manager` 縺ｮ繝｡繧ｽ繝・ラ繧剃ｽｿ逕ｨ縺吶ｋ蠢・ｦ√′縺ゅｋ

### TypeError: object AsyncSession can't be used in 'await' expression

**蜴溷屏**: `get_async_session()` 縺ｮ謌ｻ繧雁､繧定ｪ､縺｣縺ｦ await 縺励※縺・∪縺吶・

**髢馴＆縺｣縺滉ｾ・*:
```python
session = await get_async_session()  # 笶・縺薙・譎らせ縺ｧ譌｢縺ｫ AsyncSession
```

**豁｣縺励＞萓・*:
```python
session = await get_async_session()  # 笨・get_async_session() 閾ｪ菴薙′ async 髢｢謨ｰ
await session.execute(...)           # 笨・execute 繧・await
```

### ImportError: cannot import name 'AsyncSession'

**蜴溷屏**: 髱槫酔譛溘ラ繝ｩ繧､繝舌・縺後う繝ｳ繧ｹ繝医・繝ｫ縺輔ｌ縺ｦ縺・∪縺帙ｓ縲・

**隗｣豎ｺ譁ｹ豕・*:
```bash
poetry add aiosqlite  # SQLite 縺ｮ蝣ｴ蜷・
poetry add asyncpg    # PostgreSQL 縺ｮ蝣ｴ蜷・
```

### RuntimeError: Event loop is closed

**蜴溷屏**: pytest-asyncio 縺ｮ險ｭ螳壹′荳崎ｶｳ縺励※縺・∪縺吶・

**隗｣豎ｺ譁ｹ豕・*:
```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

## 髱槫酔譛溽沿縺ｮ繧ｻ繝・す繝ｧ繝ｳ邂｡逅・ヱ繧ｿ繝ｼ繝ｳ

### AsyncBaseRepository 縺ｮ繧ｻ繝・す繝ｧ繝ｳ邂｡逅・

髱槫酔譛溽沿縺ｮ `AsyncBaseRepository` 繧ょ酔讒倥↓ `session=None` 繧定ｨｱ螳ｹ縺励∵沐霆溘↑繧ｻ繝・す繝ｧ繝ｳ邂｡逅・′蜿ｯ閭ｽ縺ｧ縺吶・

### 髱槫酔譛溘ヱ繧ｿ繝ｼ繝ｳ 1: FastAPI 縺ｧ縺ｮ菴ｿ逕ｨ・域耳螂ｨ・・

**迚ｹ蠕ｴ**:
- 笨・`lifespan_context()` 縺ｧ閾ｪ蜍慕噪縺ｫ繧ｨ繝ｳ繧ｸ繝ｳ繧偵け繝ｪ繝ｼ繝ｳ繧｢繝・・
- 笨・`Depends` 繝代ち繝ｼ繝ｳ縺ｧ繧ｷ繝ｳ繝励Ν縺ｫ邨ｱ蜷・
- 笨・`dispose_async()` 縺ｮ謇句虚蜻ｼ縺ｳ蜃ｺ縺嶺ｸ崎ｦ・

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from repom.database import get_async_db_session, get_lifespan_manager
from repom.async_base_repository import AsyncBaseRepository
from your_project.models import Task

# lifespan 縺ｧ閾ｪ蜍輔け繝ｪ繝ｼ繝ｳ繧｢繝・・
app = FastAPI(lifespan=get_lifespan_manager())

@app.get("/tasks/{task_id}")
async def get_task(
    task_id: int,
    session: AsyncSession = Depends(get_async_db_session)
):
    repo = AsyncBaseRepository(Task, session)
    task = await repo.get_by_id(task_id)
    return task
```

**繝昴う繝ｳ繝・*:
- `lifespan=get_lifespan_manager()` 縺・shutdown 譎ゅ↓閾ｪ蜍慕噪縺ｫ `dispose_all()` 繧貞他縺ｶ
- 繧ｨ繝ｳ繧ｸ繝ｳ縺ｮ繧ｯ繝ｪ繝ｼ繝ｳ繧｢繝・・繧呈ｰ励↓縺吶ｋ蠢・ｦ√↑縺・

---

### 髱槫酔譛溘ヱ繧ｿ繝ｼ繝ｳ 2: 繧ｹ繧ｿ繝ｳ繝峨い繝ｭ繝ｳ繧ｹ繧ｯ繝ｪ繝励ヨ・・LI縲√ヰ繝・メ縲゛upyter・・

**迚ｹ蠕ｴ**:
- 笨・閾ｪ蜍慕噪縺ｫ `dispose_async()` 繧貞他縺ｶ
- 笨・繝励Ο繧ｰ繝ｩ繝縺梧ｭ｣蟶ｸ縺ｫ邨ゆｺ・☆繧・
- 笨・CLI 繝・・繝ｫ縲√ヰ繝・メ繧ｹ繧ｯ繝ｪ繝励ヨ縺ｫ譛驕ｩ

**笶・繧医￥縺ゅｋ蝠城｡・*:

```python
# 笶・縺薙ｌ縺ｯ繝励Ο繧ｰ繝ｩ繝縺檎ｵゆｺ・＠縺ｪ縺・
import asyncio
from repom.database import _db_manager

async def main():
    async with _db_manager.get_async_transaction() as session:
        # 繝・・繧ｿ繝吶・繧ｹ謫堺ｽ・
        pass
    # 縺薙％縺ｧ邨ゆｺ・☆繧九・縺壹□縺後√・繝ｭ繧ｰ繝ｩ繝縺悟●豁｢縺励↑縺・

if __name__ == "__main__":
    asyncio.run(main())  # 繝上Φ繧ｰ縺吶ｋ
```

**逅・罰**: SQLAlchemy 縺ｮ髱槫酔譛溘お繝ｳ繧ｸ繝ｳ縺ｯ謗･邯壹・繝ｼ繝ｫ縺ｨ繝舌ャ繧ｯ繧ｰ繝ｩ繧ｦ繝ｳ繝峨ち繧ｹ繧ｯ繧剃ｿ晄戟縺礼ｶ壹￠繧九◆繧√∵・遉ｺ逧・↓ `dispose_async()` 繧貞他縺ｰ縺ｪ縺・→邨ゆｺ・＠縺ｾ縺帙ｓ縲・

**笨・隗｣豎ｺ譁ｹ豕・1: `get_standalone_async_transaction()` 繧剃ｽｿ縺・ｼ域耳螂ｨ・・*:

```python
import asyncio
from repom.database import get_standalone_async_transaction
from sqlalchemy import select
from your_project.models import Task

async def main():
    async with get_standalone_async_transaction() as session:
        # 繝・・繧ｿ繝吶・繧ｹ謫堺ｽ・
        result = await session.execute(select(Task).limit(10))
        tasks = result.scalars().all()
        for task in tasks:
            print(task.title)
    # 閾ｪ蜍慕噪縺ｫ dispose_async() 縺悟他縺ｰ繧後ｋ

if __name__ == "__main__":
    asyncio.run(main())
```

**笨・隗｣豎ｺ譁ｹ豕・2: 謇句虚縺ｧ `dispose_async()` 繧貞他縺ｶ**:

```python
import asyncio
from repom.database import _db_manager

async def main():
    try:
        async with _db_manager.get_async_transaction() as session:
            # 繝・・繧ｿ繝吶・繧ｹ謫堺ｽ・
            pass
    finally:
        # 謗･邯壹・繝ｼ繝ｫ繧偵け繝ｪ繝ｼ繝ｳ繧｢繝・・・亥ｿ・茨ｼ・ｼ・
        await _db_manager.dispose_async()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 髱槫酔譛溘ヱ繧ｿ繝ｼ繝ｳ縺ｮ驕ｸ謚槭ぎ繧､繝・

| 繝ｦ繝ｼ繧ｹ繧ｱ繝ｼ繧ｹ | 謗ｨ螂ｨ繝代ち繝ｼ繝ｳ | 繧ｯ繝ｪ繝ｼ繝ｳ繧｢繝・・ |
|-------------|-------------|---------------|
| **FastAPI 繧｢繝励Μ** | `get_async_db_session()` + `lifespan` | 閾ｪ蜍・|
| **CLI 繝・・繝ｫ** | `get_standalone_async_transaction()` | 閾ｪ蜍・|
| **繝舌ャ繝√せ繧ｯ繝ｪ繝励ヨ** | `get_standalone_async_transaction()` | 閾ｪ蜍・|
| **Jupyter Notebook** | `get_standalone_async_transaction()` | 閾ｪ蜍・|
| **pytest 縺ｧ縺ｮ髱槫酔譛溘ユ繧ｹ繝・* | fixture + `dispose_async()` | fixture 縺ｧ邂｡逅・|

---

### 髱槫酔譛溽沿縺ｮ繝吶せ繝医・繝ｩ繧ｯ繝・ぅ繧ｹ

#### 笨・DO: FastAPI 縺ｧ縺ｯ lifespan 繧剃ｽｿ縺・

```python
# Good: lifespan 縺瑚・蜍慕噪縺ｫ繧ｯ繝ｪ繝ｼ繝ｳ繧｢繝・・
from fastapi import FastAPI
from repom.database import get_lifespan_manager

app = FastAPI(lifespan=get_lifespan_manager())
```

#### 笨・DO: 繧ｹ繧ｿ繝ｳ繝峨い繝ｭ繝ｳ繧ｹ繧ｯ繝ｪ繝励ヨ縺ｧ縺ｯ蟆ら畑繝倥Ν繝代・繧剃ｽｿ縺・

```python
# Good: 閾ｪ蜍慕噪縺ｫ dispose 縺輔ｌ繧・
import asyncio
from repom.database import get_standalone_async_transaction

async def main():
    async with get_standalone_async_transaction() as session:
        # 蜃ｦ逅・

asyncio.run(main())
```

#### 笶・DON'T: 繧ｹ繧ｿ繝ｳ繝峨い繝ｭ繝ｳ縺ｧ dispose 繧貞ｿ倥ｌ繧・

```python
# Bad: 繝励Ο繧ｰ繝ｩ繝縺檎ｵゆｺ・＠縺ｪ縺・
async with _db_manager.get_async_transaction() as session:
    pass
# dispose_async() 繧貞他繧薙〒縺・↑縺・
```

---

## 縺ｾ縺ｨ繧・

**隕壹∴縺ｦ縺翫￥縺ｹ縺・3 縺､縺ｮ繝昴う繝ｳ繝・*:

1. **`session=None` 縺ｯ OK** - BaseRepository 縺瑚・蜍慕噪縺ｫ蜃ｦ逅・＠縺ｾ縺・
2. **繧ｷ繝ｳ繝励Ν縺ｪ謫堺ｽ懊・繝代ち繝ｼ繝ｳ 1** - 繧ｻ繝・す繝ｧ繝ｳ繧呈ｸ｡縺輔★縲√◎縺ｮ縺ｾ縺ｾ菴ｿ縺・
3. **隍・焚謫堺ｽ懊・繝代ち繝ｼ繝ｳ 2** - `get_db_transaction()` 縺ｧ繝ｩ繝・・縺吶ｋ

**蝓ｺ譛ｬ繝ｫ繝ｼ繝ｫ・亥酔譛溽沿・・*:
- 蜊倡ｴ斐↑謫堺ｽ・竊・繧ｻ繝・す繝ｧ繝ｳ縺ｪ縺・
- 隍・尅縺ｪ謫堺ｽ・竊・譏守､ｺ逧・ヨ繝ｩ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ
- FastAPI 竊・Depends 繝代ち繝ｼ繝ｳ

**蝓ｺ譛ｬ繝ｫ繝ｼ繝ｫ・磯撼蜷梧悄迚茨ｼ・*:
- FastAPI 竊・`get_async_db_session()` + `lifespan_context()`
- CLI/繝舌ャ繝・竊・`get_standalone_async_transaction()`
- 謇句虚邂｡逅・竊・`get_async_transaction()` + `dispose_async()`

**驕ｿ縺代ｋ縺ｹ縺阪％縺ｨ**:
- 笶・Repository 縺ｮ `__init__` 縺ｧ `session is None` 繝√ぉ繝・け縺励※ raise
- 笶・`__init__` 縺ｧ `get_db_session()` 繧堤峩謗･蜻ｼ縺ｶ
- 笶・繝代ち繝ｼ繝ｳ 1 縺ｧ隍・焚謫堺ｽ懊ｒ螳溯｡・
- 笶・繧ｹ繧ｿ繝ｳ繝峨い繝ｭ繝ｳ繧ｹ繧ｯ繝ｪ繝励ヨ縺ｧ `dispose_async()` 繧貞ｿ倥ｌ繧・

---

## 髢｢騾｣繝峨く繝･繝｡繝ｳ繝・

- [repository_and_utilities_guide.md](repository_and_utilities_guide.md) - BaseRepository 縺ｮ蝓ｺ譛ｬ逧・↑菴ｿ縺・婿
- [async_repository_guide.md](async_repository_guide.md) - 髱槫酔譛溽沿 Repository 縺ｮ菴ｿ縺・婿
