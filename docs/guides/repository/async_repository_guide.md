# AsyncBaseRepository 繧ｬ繧､繝・

**逶ｮ逧・*: repom 縺ｮ `AsyncBaseRepository` 縺ｫ繧医ｋ髱槫酔譛溘ョ繝ｼ繧ｿ繧｢繧ｯ繧ｻ繧ｹ繝代ち繝ｼ繝ｳ繧堤炊隗｣縺吶ｋ

**蟇ｾ雎｡隱ｭ閠・*: FastAPI 縺ｪ縺ｩ髱槫酔譛溘ヵ繝ｬ繝ｼ繝繝ｯ繝ｼ繧ｯ縺ｧ repom 繧剃ｽｿ縺・幕逋ｺ閠・・AI 繧ｨ繝ｼ繧ｸ繧ｧ繝ｳ繝・

---

## 答 逶ｮ谺｡

1. [縺ｯ縺倥ａ縺ｫ](#縺ｯ縺倥ａ縺ｫ)
2. [蝓ｺ譛ｬ逧・↑菴ｿ縺・婿](#蝓ｺ譛ｬ逧・↑菴ｿ縺・婿)
3. [FastAPI 邨ｱ蜷・(#fastapi-邨ｱ蜷・
4. [髱槫酔譛・CRUD 謫堺ｽ彎(#髱槫酔譛・crud-謫堺ｽ・
5. [讀懃ｴ｢縺ｨ繝輔ぅ繝ｫ繧ｿ繝ｪ繝ｳ繧ｰ](#讀懃ｴ｢縺ｨ繝輔ぅ繝ｫ繧ｿ繝ｪ繝ｳ繧ｰ)
6. [Eager Loading・・+1 蝠城｡後・隗｣豎ｺ・云(#eager-loading)
7. [荳ｦ陦悟・逅・ヱ繧ｿ繝ｼ繝ｳ](#荳ｦ陦悟・逅・ヱ繧ｿ繝ｼ繝ｳ)
8. [繝吶せ繝医・繝ｩ繧ｯ繝・ぅ繧ｹ](#繝吶せ繝医・繝ｩ繧ｯ繝・ぅ繧ｹ)

---

## 縺ｯ縺倥ａ縺ｫ

### AsyncBaseRepository 縺ｨ縺ｯ

`AsyncBaseRepository` 縺ｯ `BaseRepository` 縺ｮ螳悟・髱槫酔譛溽沿縺ｧ縺吶ゅ☆縺ｹ縺ｦ縺ｮ繝｡繧ｽ繝・ラ縺・`async def` 縺ｧ螳夂ｾｩ縺輔ｌ縲～AsyncSession` 繧剃ｽｿ逕ｨ縺励※繝・・繧ｿ繝吶・繧ｹ謫堺ｽ懊ｒ陦後＞縺ｾ縺吶・

### BaseRepository 縺ｨ縺ｮ驕輔＞

| 鬆・岼 | BaseRepository | AsyncBaseRepository |
|------|----------------|---------------------|
| 繧ｻ繝・す繝ｧ繝ｳ蝙・| `Session` | `AsyncSession` |
| 繝｡繧ｽ繝・ラ | 蜷梧悄・磯壼ｸｸ縺ｮ髢｢謨ｰ・・| 髱槫酔譛滂ｼ・async def`・・|
| 蜻ｼ縺ｳ蜃ｺ縺・| `repo.find()` | `await repo.find()` |
| 逕ｨ騾・| 蜷梧悄繧｢繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ | FastAPI, 髱槫酔譛溘い繝励Μ |

### 縺・▽菴ｿ縺・°

笨・**AsyncBaseRepository 繧剃ｽｿ縺・∋縺榊ｴ蜷・*:
- FastAPI 縺ｪ縺ｩ縺ｮ髱槫酔譛溘ヵ繝ｬ繝ｼ繝繝ｯ繝ｼ繧ｯ
- 鬮倅ｸｦ陦梧ｧ縺梧ｱゅａ繧峨ｌ繧九い繝励Μ繧ｱ繝ｼ繧ｷ繝ｧ繝ｳ
- I/O 繝舌え繝ｳ繝峨↑蜃ｦ逅・′螟壹＞蝣ｴ蜷・
- asyncio.gather 縺ｧ荳ｦ陦悟・逅・＠縺溘＞蝣ｴ蜷・

笶・**BaseRepository 縺ｧ蜊∝・縺ｪ蝣ｴ蜷・*:
- 繧ｹ繧ｯ繝ｪ繝励ヨ繧・ヰ繝・メ蜃ｦ逅・
- 蜊倡ｴ斐↑ CRUD 謫堺ｽ懊・縺ｿ
- 荳ｦ陦梧ｧ縺御ｸ崎ｦ√↑蝣ｴ蜷・

---

## 蝓ｺ譛ｬ逧・↑菴ｿ縺・婿

### 繝ｪ繝昴ず繝医Μ縺ｮ菴懈・

```python
from repom import AsyncBaseRepository
from repom.database import get_async_db_session
from your_project.models import Task
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

# FastAPI Depends 繝代ち繝ｼ繝ｳ縺ｧ菴ｿ逕ｨ・域耳螂ｨ・・
async def get_task(task_id: int, session: AsyncSession = Depends(get_async_db_session)):
    repo = AsyncBaseRepository(Task, session)
    task = await repo.get_by_id(task_id)
    return task
```

### 荳ｻ隕√Γ繧ｽ繝・ラ荳隕ｧ

縺吶∋縺ｦ縺ｮ繝｡繧ｽ繝・ラ縺ｯ `async def` 縺ｧ縲～await` 縺悟ｿ・ｦ√〒縺吶・

| 繝｡繧ｽ繝・ラ | 逕ｨ騾・| 謌ｻ繧雁､ |
|---------|------|--------|
| `await get_by_id(id)` | ID 縺ｧ蜿門ｾ・| `Optional[T]` |
| `await get_by(column, value)` | 繧ｫ繝ｩ繝縺ｧ讀懃ｴ｢ | `List[T]` |
| `await get_all()` | 蜈ｨ莉ｶ蜿門ｾ・| `List[T]` |
| `await find(filters, **options)` | 譚｡莉ｶ讀懃ｴ｢ | `List[T]` |
| `await find_one(filters)` | 蜊倅ｸ讀懃ｴ｢ | `Optional[T]` |
| `await count(filters)` | 莉ｶ謨ｰ繧ｫ繧ｦ繝ｳ繝・| `int` |
| `await save(instance)` | 菫晏ｭ・| `T` |
| `await saves(instances)` | 荳諡ｬ菫晏ｭ・| `None` |
| `await remove(instance)` | 蜑企勁 | `None` |
| `await soft_delete(id)` | 隲也炊蜑企勁 | `bool` |
| `await restore(id)` | 蠕ｩ蜈・| `bool` |
| `await find_deleted()` | 蜑企勁貂医∩蜿門ｾ・| `List[T]` |

---

## FastAPI 邨ｱ蜷・

### 蝓ｺ譛ｬ逧・↑邨ｱ蜷医ヱ繧ｿ繝ｼ繝ｳ

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from repom.database import get_async_db_session
from repom import AsyncBaseRepository
from your_project.models import Task

app = FastAPI()

@app.get("/tasks/{task_id}")
async def get_task(
    task_id: int,
    session: AsyncSession = Depends(get_async_db_session)
):
    repo = AsyncBaseRepository(Task, session)
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
```

### 繧ｫ繧ｹ繧ｿ繝繝ｪ繝昴ず繝医Μ繧剃ｽｿ縺・婿豕・

```python
from typing import List
from repom import AsyncBaseRepository

class TaskRepository(AsyncBaseRepository[Task]):
    """繧ｿ繧ｹ繧ｯ蟆ら畑繝ｪ繝昴ず繝医Μ"""
    
    async def find_active_tasks(self) -> List[Task]:
        """繧｢繧ｯ繝・ぅ繝悶↑繧ｿ繧ｹ繧ｯ縺ｮ縺ｿ蜿門ｾ・""
        return await self.find(filters=[Task.status == 'active'])
    
    async def find_by_user(self, user_id: int) -> List[Task]:
        """迚ｹ螳壹Θ繝ｼ繧ｶ繝ｼ縺ｮ繧ｿ繧ｹ繧ｯ繧貞叙蠕・""
        return await self.find(filters=[Task.user_id == user_id])

# FastAPI 縺ｧ菴ｿ逕ｨ
@app.get("/tasks/active")
async def get_active_tasks(session: AsyncSession = Depends(get_async_db_session)):
    repo = TaskRepository(Task, session)
    return await repo.find_active_tasks()
```

### 繝ｪ繝昴ず繝医Μ繧・Depends 縺ｧ豕ｨ蜈･

```python
from typing import Annotated

def get_task_repo(session: AsyncSession = Depends(get_async_db_session)):
    return TaskRepository(Task, session)

TaskRepoDep = Annotated[TaskRepository, Depends(get_task_repo)]

@app.get("/tasks")
async def list_tasks(repo: TaskRepoDep):
    return await repo.find()

@app.get("/tasks/{task_id}")
async def get_task(task_id: int, repo: TaskRepoDep):
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404)
    return task
```

---

## 髱槫酔譛・CRUD 謫堺ｽ・

### Create・井ｽ懈・・・

```python
# FastAPI 繧ｨ繝ｳ繝峨・繧､繝ｳ繝医〒縺ｮ菴ｿ逕ｨ萓・
@app.post("/tasks")
async def create_task(
    task_data: dict,
    session: AsyncSession = Depends(get_async_db_session)
):
    repo = AsyncBaseRepository(Task, session)
    
    # 1莉ｶ菫晏ｭ・
    task = Task(title=task_data["title"], status="active")
    saved_task = await repo.save(task)
    
    # 霎樊嶌縺九ｉ菫晏ｭ・
    task = await repo.dict_save({"title": "繧ｿ繧ｹ繧ｯ2", "status": "pending"})
    
    # 隍・焚菫晏ｭ・
    tasks = [Task(title=f"繧ｿ繧ｹ繧ｯ{i}") for i in range(3)]
    await repo.saves(tasks)
    
    # 霎樊嶌繝ｪ繧ｹ繝医°繧我ｿ晏ｭ・
    data_list = [{"title": f"繧ｿ繧ｹ繧ｯ{i}"} for i in range(3)]
    await repo.dict_saves(data_list)
    
    return saved_task
```

### Read・亥叙蠕暦ｼ・

```python
# FastAPI 繧ｨ繝ｳ繝峨・繧､繝ｳ繝医〒縺ｮ菴ｿ逕ｨ萓・
@app.get("/tasks/{task_id}")
async def get_task(
    task_id: int,
    session: AsyncSession = Depends(get_async_db_session)
):
    repo = AsyncBaseRepository(Task, session)
    
    # ID 縺ｧ蜿門ｾ・
    task = await repo.get_by_id(task_id)
    
    # 繧ｫ繝ｩ繝縺ｧ讀懃ｴ｢・郁､・焚莉ｶ・・
    active_tasks = await repo.get_by('status', 'active')
    
    # 蜊倅ｸ蜿門ｾ暦ｼ・ingle=True・・
        task = await repo.get_by('title', '繧ｿ繧ｹ繧ｯ1', single=True)
        
        # 蜈ｨ莉ｶ蜿門ｾ・
        all_tasks = await repo.get_all()
```

### Update・域峩譁ｰ・・

```python
async def update_task(task_id: int):
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # 繧､繝ｳ繧ｹ繧ｿ繝ｳ繧ｹ繧貞叙蠕励＠縺ｦ譖ｴ譁ｰ
        task = await repo.get_by_id(task_id)
        if task:
            task.status = 'completed'
            await repo.save(task)
        
        # 縺ｾ縺溘・ BaseModel 縺ｮ update_from_dict 繧剃ｽｿ逕ｨ
        task.update_from_dict({"status": "completed"})
        await repo.save(task)
```

### Delete・亥炎髯､・・

```python
async def delete_task(task_id: int):
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # 迚ｩ逅・炎髯､・亥ｮ悟・蜑企勁・・
        task = await repo.get_by_id(task_id)
        if task:
            await repo.remove(task)
```

---

## 讀懃ｴ｢縺ｨ繝輔ぅ繝ｫ繧ｿ繝ｪ繝ｳ繧ｰ

髱槫酔譛溽沿縺ｧ繧よ､懃ｴ｢繝ｻ繝輔ぅ繝ｫ繧ｿ繝ｪ繝ｳ繧ｰ讖溯・縺ｯ蜷梧悄迚医→蜷後§縺ｧ縺吶りｩｳ邏ｰ縺ｯ **[Repository 荳顔ｴ壹ぎ繧､繝云(repository_advanced_guide.md)** 繧貞盾辣ｧ縺励※縺上□縺輔＞縲・

### 繧ｯ繧､繝・け繝ｪ繝輔ぃ繝ｬ繝ｳ繧ｹ

```python
async with get_async_db_session() as session:
    repo = AsyncBaseRepository(Task, session)
    
    # 蝓ｺ譛ｬ讀懃ｴ｢
    tasks = await repo.find(filters=[Task.status == 'active'])
    
    # 繝壹・繧ｸ繝阪・繧ｷ繝ｧ繝ｳ
    tasks = await repo.find(offset=0, limit=20, order_by='created_at:desc')
    
    # 繧ｫ繧ｦ繝ｳ繝・
    count = await repo.count(filters=[Task.status == 'active'])
```

隧ｳ邏ｰ縺ｪ繝輔ぅ繝ｫ繧ｿ繝ｪ繝ｳ繧ｰ繝代ち繝ｼ繝ｳ・・ND/OR縲´IKE縲！N蜿･縺ｪ縺ｩ・峨・ [Repository 荳顔ｴ壹ぎ繧､繝云(repository_advanced_guide.md#讀懃ｴ｢縺ｨ繝輔ぅ繝ｫ繧ｿ繝ｪ繝ｳ繧ｰ) 繧貞盾辣ｧ縺励※縺上□縺輔＞縲・

---

## Eager Loading・・+1 蝠城｡後・隗｣豎ｺ・・

髱槫酔譛溽沿縺ｧ繧・Eager Loading 縺ｮ莉慕ｵ・∩縺ｯ蜷梧悄迚医→蜷後§縺ｧ縺吶りｩｳ邏ｰ縺ｯ **[Repository 荳顔ｴ壹ぎ繧､繝云(repository_advanced_guide.md#eager-loadingn1蝠城｡後・隗｣豎ｺ)** 繧貞盾辣ｧ縺励※縺上□縺輔＞縲・

### 繧ｯ繧､繝・け繝ｪ繝輔ぃ繝ｬ繝ｳ繧ｹ

```python
from sqlalchemy.orm import joinedload, selectinload

# find() 縺ｧ菴ｿ逕ｨ
tasks = await repo.find(
    filters=[Task.status == 'active'],
    options=[joinedload(Task.user)]
)

# get_by_id() 縺ｧ菴ｿ逕ｨ・・EW!・・
task = await repo.get_by_id(1, options=[
    joinedload(Task.user),
    selectinload(Task.comments)
])

# get_by() 縺ｧ菴ｿ逕ｨ・・EW!・・
task = await repo.get_by('title', '繧ｿ繧ｹ繧ｯ1', single=True, options=[
    joinedload(Task.user)
])

# find_one() 縺ｧ菴ｿ逕ｨ・・EW!・・
task = await repo.find_one(
    filters=[Task.id == 1],
    options=[joinedload(Task.user)]
)
```

隧ｳ邏ｰ縺ｪ菴ｿ縺・婿縲√ヱ繝輔か繝ｼ繝槭Φ繧ｹ豈碑ｼ・√・繧ｹ繝医・繝ｩ繧ｯ繝・ぅ繧ｹ縺ｯ [Repository 荳顔ｴ壹ぎ繧､繝云(repository_advanced_guide.md#eager-loadingn1蝠城｡後・隗｣豎ｺ) 繧貞盾辣ｧ縺励※縺上□縺輔＞縲・

### default_options 縺ｫ繧医ｋ閾ｪ蜍暮←逕ｨ

```python
class TaskRepository(AsyncBaseRepository[Task]):
    # 繧ｯ繝ｩ繧ｹ螻樊ｧ縺ｧ謖・ｮ夲ｼ域耳螂ｨ・・
    default_options = [
        joinedload(Task.user),
        selectinload(Task.comments)
    ]

# 縺吶∋縺ｦ縺ｮ蜿門ｾ励Γ繧ｽ繝・ラ縺ｧ閾ｪ蜍暮←逕ｨ
repo = TaskRepository(session=session)
tasks = await repo.find()  # user 縺ｨ comments 縺瑚・蜍輔Ο繝ｼ繝・
task = await repo.get_by_id(1)  # 蜷後§縺剰・蜍暮←逕ｨ
```

隧ｳ邏ｰ縺ｯ [Repository 荳顔ｴ壹ぎ繧､繝云(repository_advanced_guide.md#eager-loadingn1蝠城｡後・隗｣豎ｺ) 繧貞盾辣ｧ縺励※縺上□縺輔＞縲・

---

## 繧ｫ繧ｹ繧ｿ繝繝ｪ繝昴ず繝医Μ

繝薙ず繝阪せ繝ｭ繧ｸ繝・け繧貞性繧繧ｫ繧ｹ繧ｿ繝繝ｪ繝昴ず繝医Μ縺ｮ菴懈・譁ｹ豕輔・ **[Repository 荳顔ｴ壹ぎ繧､繝云(repository_advanced_guide.md#繧ｫ繧ｹ繧ｿ繝繝ｪ繝昴ず繝医Μ)** 繧貞盾辣ｧ縺励※縺上□縺輔＞縲・

### 繧ｯ繧､繝・け繝ｪ繝輔ぃ繝ｬ繝ｳ繧ｹ

```python
class TaskRepository(AsyncBaseRepository[Task]):
    async def find_active(self) -> List[Task]:
        return await self.find(filters=[Task.status == 'active'])
    
    async def find_overdue(self) -> List[Task]:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return await self.find(
            filters=[
                Task.status != 'completed',
                Task.due_date < now
            ]
        )
```

隍・尅縺ｪ讀懃ｴ｢繝ｭ繧ｸ繝・け縲・未騾｣繝｢繝・Ν謫堺ｽ懊√ン繧ｸ繝阪せ繝ｭ繧ｸ繝・け邨ｱ蜷医・隧ｳ邏ｰ縺ｯ [Repository 荳顔ｴ壹ぎ繧､繝云(repository_advanced_guide.md#繧ｫ繧ｹ繧ｿ繝繝ｪ繝昴ず繝医Μ) 繧貞盾辣ｧ縺励※縺上□縺輔＞縲・

---

## 隲也炊蜑企勁・・oftDelete・・

隲也炊蜑企勁讖溯・縺ｮ菴ｿ縺・婿縺ｯ **[SoftDelete 繧ｬ繧､繝云(repository_soft_delete_guide.md)** 繧貞盾辣ｧ縺励※縺上□縺輔＞縲る撼蜷梧悄迚医・螳溯｣・ｾ九ｂ蜷ｫ縺ｾ繧後※縺・∪縺吶・

### 繧ｯ繧､繝・け繝ｪ繝輔ぃ繝ｬ繝ｳ繧ｹ

```python
# 隲也炊蜑企勁
await repo.soft_delete(task_id)

# 蠕ｩ蜈・
await repo.restore(task_id)

# 蜑企勁貂医∩繧貞性繧√※讀懃ｴ｢
tasks = await repo.find(include_deleted=True)

# 蜑企勁貂医∩縺ｮ縺ｿ蜿門ｾ・
deleted_tasks = await repo.find_deleted()
```

隧ｳ邏ｰ縺ｯ [SoftDelete 繧ｬ繧､繝云(repository_soft_delete_guide.md) 繧貞盾辣ｧ縺励※縺上□縺輔＞縲・

---

## 髱槫酔譛溽音譛峨・讖溯・

莉･荳九・繧ｻ繧ｯ繧ｷ繝ｧ繝ｳ縺ｯ AsyncBaseRepository 縺ｫ迚ｹ譛峨・讖溯・縺ｧ縺吶・

---

## 荳ｦ陦悟・逅・ヱ繧ｿ繝ｼ繝ｳ

### asyncio.gather 縺ｫ繧医ｋ荳ｦ陦悟ｮ溯｡・

```python
import asyncio

async def fetch_multiple_resources():
    async with get_async_db_session() as session:
        task_repo = AsyncBaseRepository(Task, session)
        user_repo = AsyncBaseRepository(User, session)
        project_repo = AsyncBaseRepository(Project, session)
        
        # 3縺､縺ｮ繧ｯ繧ｨ繝ｪ繧剃ｸｦ陦悟ｮ溯｡・
        tasks, users, projects = await asyncio.gather(
            task_repo.find(filters=[Task.status == 'active']),
            user_repo.get_all(),
            project_repo.find(limit=10)
        )
        
        return {
            "tasks": tasks,
            "users": users,
            "projects": projects
        }
```
):
    repo = TaskRepository(session=session)
    task = await repo.get_by_id(task_id)  # default_options 驕ｩ逕ｨ
    if not task:
        raise HTTPException(status_code=404)
    return task
```

### 繝代ヵ繧ｩ繝ｼ繝槭Φ繧ｹ縺ｸ縺ｮ蠖ｱ髻ｿ

**繝｡繝ｪ繝・ヨ・・+1 蝠城｡後・隗｣豎ｺ・・*:

```python
# Without default_options
tasks = await repo.find()  # 1蝗槭・繧ｯ繧ｨ繝ｪ
for task in tasks:
    print(task.user.name)  # N蝗槭・繧ｯ繧ｨ繝ｪ・・+1 蝠城｡鯉ｼ・
# 蜷郁ｨ・ 1 + N = 101蝗槭・繧ｯ繧ｨ繝ｪ・・=100縺ｮ蝣ｴ蜷茨ｼ・

# With default_options
class TaskRepository(AsyncBaseRepository[Task]):
    def __init__(self, session: AsyncSession):
        super().__init__(Task, session)
        self.default_options = [joinedload(Task.user)]

tasks = await repo.find()  # 2蝗槭・繧ｯ繧ｨ繝ｪ・・asks 縺ｨ users・・
for task in tasks:
    print(task.user.name)  # 繧ｯ繧ｨ繝ｪ縺ｪ縺・
# 蜷郁ｨ・ 2蝗槭・繧ｯ繧ｨ繝ｪ・・=100縺ｧ繧ょ酔縺假ｼ・
```

**繝・Γ繝ｪ繝・ヨ・井ｸ崎ｦ√↑ eager load・・*:

繝ｪ繝ｬ繝ｼ繧ｷ繝ｧ繝ｳ繧剃ｽｿ繧上↑縺・ｴ蜷医〒繧・eager load 縺檎匱逕溘＠縺ｾ縺吶ゅ◎縺ｮ蝣ｴ蜷医・ `options=[]` 縺ｧ辟｡蜉ｹ蛹厄ｼ・

```python
# 繝ｪ繝ｬ繝ｼ繧ｷ繝ｧ繝ｳ荳崎ｦ√↑蝣ｴ蜷医・譏守､ｺ逧・↓繧ｹ繧ｭ繝・・
task_ids = [task.id for task in await repo.find(options=[])]  # 鬮倬・
```

### 繝吶せ繝医・繝ｩ繧ｯ繝・ぅ繧ｹ

| 迥ｶ豕・| 謗ｨ螂ｨ險ｭ螳・| 逅・罰 |
|------|---------|------|
| 繝ｪ繝ｬ繝ｼ繧ｷ繝ｧ繝ｳ繧帝ｻ郢√↓菴ｿ縺・| `default_options` 縺ｧ險ｭ螳・| N+1 蝠城｡後ｒ閾ｪ蜍慕噪縺ｫ蝗樣∩ |
| 繝ｪ繝ｬ繝ｼ繧ｷ繝ｧ繝ｳ繧偵◆縺ｾ縺ｫ菴ｿ縺・| `default_options` 縺ｪ縺・| 蠢・ｦ√↓蠢懊§縺ｦ `options` 繧呈欠螳・|
| 繝代ヵ繧ｩ繝ｼ繝槭Φ繧ｹ縺碁㍾隕・| 繧ｱ繝ｼ繧ｹ繝舌う繧ｱ繝ｼ繧ｹ縺ｧ `options` 繧呈欠螳・| 譟碑ｻ溘↑譛驕ｩ蛹・|

---

### 繝代ヵ繧ｩ繝ｼ繝槭Φ繧ｹ豈碑ｼ・

| 譁ｹ豕・| 繧ｯ繧ｨ繝ｪ謨ｰ | 繝代ヵ繧ｩ繝ｼ繝槭Φ繧ｹ |
|-----|---------|--------------|
| Lazy loading | N+1 蝗・| 笶・驕・＞ |
| joinedload | 1蝗橸ｼ・OIN・・| 笨・騾溘＞ |
| selectinload | 2蝗橸ｼ・N・・| 笨・騾溘＞ |

**謗ｨ螂ｨ**:
- 螟壼ｯｾ荳・・Task.user`・・ `joinedload`
- 荳蟇ｾ螟夲ｼ・Project.tasks`・・ `selectinload`

---

## 荳ｦ陦悟・逅・ヱ繧ｿ繝ｼ繝ｳ

### asyncio.gather 縺ｫ繧医ｋ荳ｦ陦悟ｮ溯｡・

```python
import asyncio

async def fetch_multiple_resources():
    async with get_async_db_session() as session:
        task_repo = AsyncBaseRepository(Task, session)
        user_repo = AsyncBaseRepository(User, session)
        project_repo = AsyncBaseRepository(Project, session)
        
        # 3縺､縺ｮ繧ｯ繧ｨ繝ｪ繧剃ｸｦ陦悟ｮ溯｡・
        tasks, users, projects = await asyncio.gather(
            task_repo.find(filters=[Task.status == 'active']),
            user_repo.get_all(),
            project_repo.find(limit=10)
        )
        
        return {
            "tasks": tasks,
            "users": users,
            "projects": projects
        }
```

### FastAPI 縺ｧ縺ｮ荳ｦ陦悟・逅・

```python
@app.get("/dashboard")
async def get_dashboard(session: AsyncSession = Depends(get_async_db_session)):
    task_repo = AsyncBaseRepository(Task, session)
    user_repo = AsyncBaseRepository(User, session)
    
    # 隍・焚縺ｮ繧ｫ繧ｦ繝ｳ繝医ｒ荳ｦ陦悟ｮ溯｡・
    total_tasks, active_tasks, total_users = await asyncio.gather(
        task_repo.count(),
        task_repo.count(filters=[Task.status == 'active']),
        user_repo.count()
    )
    
    return {
        "total_tasks": total_tasks,
        "active_tasks": active_tasks,
        "total_users": total_users
    }
```

### 繧ｨ繝ｩ繝ｼ繝上Φ繝峨Μ繝ｳ繧ｰ莉倥″荳ｦ陦悟・逅・

```python
async def fetch_with_fallback():
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        try:
            results = await asyncio.gather(
                repo.get_by_id(1),
                repo.get_by_id(2),
                repo.get_by_id(3),
                return_exceptions=True  # 繧ｨ繝ｩ繝ｼ繧剃ｾ句､悶→縺励※霑斐☆
            )
            
            # 謌仙粥縺励◆繧ゅ・縺縺代ヵ繧｣繝ｫ繧ｿ
            valid_results = [r for r in results if not isinstance(r, Exception)]
            return valid_results
        except Exception as e:
            logger.error(f"Error fetching tasks: {e}")
            return []
```

### 繝舌ャ繝∝・逅・ヱ繧ｿ繝ｼ繝ｳ

```python
async def process_tasks_in_batches(task_ids: List[int], batch_size: int = 10):
    """螟ｧ驥上・繧ｿ繧ｹ繧ｯ繧偵ヰ繝・メ蜃ｦ逅・""
    async with get_async_db_session() as session:
        repo = AsyncBaseRepository(Task, session)
        
        # 繝舌ャ繝√↓蛻・牡
        for i in range(0, len(task_ids), batch_size):
            batch_ids = task_ids[i:i + batch_size]
            
            # find_by_ids 縺ｧ荳諡ｬ蜿門ｾ・
            tasks = await repo.find_by_ids(batch_ids)
            
            # 蜃ｦ逅・
            for task in tasks:
                task.status = 'processed'
            
            await repo.saves(tasks)
            
            # 蟆代＠蠕・ｩ滂ｼ郁ｲ闕ｷ霆ｽ貂幢ｼ・
            await asyncio.sleep(0.1)
```

---

## 繝吶せ繝医・繝ｩ繧ｯ繝・ぅ繧ｹ

### 笨・DO: 繧ｻ繝・す繝ｧ繝ｳ邂｡逅・

```python
# Good: 繧ｳ繝ｳ繝・く繧ｹ繝医・繝阪・繧ｸ繝｣繝ｼ縺ｧ閾ｪ蜍慕ｮ｡逅・
async with get_async_db_session() as session:
    repo = AsyncBaseRepository(Task, session)
    task = await repo.get_by_id(1)
    # session 縺ｯ閾ｪ蜍慕噪縺ｫ繧ｯ繝ｭ繝ｼ繧ｺ縺輔ｌ繧・

# Good: FastAPI 縺ｮ Depends 縺ｧ豕ｨ蜈･
@app.get("/tasks")
async def list_tasks(session: AsyncSession = Depends(get_async_db_session)):
    repo = AsyncBaseRepository(Task, session)
    return await repo.find()
```

```python
# Bad: 繧ｻ繝・す繝ｧ繝ｳ繧呈焔蜍慕ｮ｡逅・ｼ医け繝ｭ繝ｼ繧ｺ蠢倥ｌ縺ｮ繝ｪ繧ｹ繧ｯ・・
session = AsyncSession(async_engine)
repo = AsyncBaseRepository(Task, session)
task = await repo.get_by_id(1)
await session.close()  # 蠢倥ｌ繧句庄閭ｽ諤ｧ
```

### 笨・DO: Eager Loading 縺ｮ菴ｿ逕ｨ

```python
# Good: N+1 蝠城｡後ｒ蝗樣∩
tasks = await repo.find(
    options=[joinedload(Task.user)]
)

# Bad: Lazy loading・・+1 蝠城｡檎匱逕滂ｼ・
tasks = await repo.find()
for task in tasks:
    print(task.user.name)  # 蜷・ち繧ｹ繧ｯ縺ｧ蛟句挨繧ｯ繧ｨ繝ｪ
```

### 笨・DO: 荳ｦ陦悟・逅・・豢ｻ逕ｨ

```python
# Good: 迢ｬ遶九＠縺溘け繧ｨ繝ｪ縺ｯ荳ｦ陦悟ｮ溯｡・
tasks, users = await asyncio.gather(
    task_repo.find(),
    user_repo.find()
)

# Bad: 鬆・ｬ｡螳溯｡鯉ｼ磯≦縺・ｼ・
tasks = await task_repo.find()
users = await user_repo.find()
```

### 笨・DO: 繧ｨ繝ｩ繝ｼ繝上Φ繝峨Μ繝ｳ繧ｰ

```python
# Good: 驕ｩ蛻・↑繧ｨ繝ｩ繝ｼ繝上Φ繝峨Μ繝ｳ繧ｰ
try:
    task = await repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await repo.save(task)
except SQLAlchemyError as e:
    logger.error(f"Database error: {e}")
    raise HTTPException(status_code=500, detail="Database error")
```

### 笨・DO: 繧ｫ繧ｹ繧ｿ繝繝ｪ繝昴ず繝医Μ縺ｮ菴懈・

```python
# Good: 繝薙ず繝阪せ繝ｭ繧ｸ繝・け繧偵Μ繝昴ず繝医Μ縺ｫ髮・ｴ・
class TaskRepository(AsyncBaseRepository[Task]):
    async def find_active_tasks(self) -> List[Task]:
        return await self.find(filters=[Task.status == 'active'])
    
    async def find_overdue_tasks(self) -> List[Task]:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return await self.find(
            filters=[
                Task.status != 'completed',
                Task.due_date < now
            ]
        )
```

### 笶・DON'T: 繝ｪ繝昴ず繝医Μ蜀・〒縺ｮ荳ｦ陦悟・逅・

```python
# Bad: 繝ｪ繝昴ず繝医Μ繝｡繧ｽ繝・ラ蜀・〒 asyncio.gather
class TaskRepository(AsyncBaseRepository[Task]):
    async def get_tasks_and_users(self):
        # 縺薙ｌ縺ｯ繧・ｉ縺ｪ縺・- 雋ｬ蜍吶′荳肴・遒ｺ
        return await asyncio.gather(
            self.find(),
            user_repo.find()  # 莉悶・繝ｪ繝昴ず繝医Μ縺ｫ萓晏ｭ・
        )

# Good: 繧ｨ繝ｳ繝峨・繧､繝ｳ繝医〒荳ｦ陦悟・逅・
@app.get("/data")
async def get_data(session: AsyncSession = Depends(get_async_db_session)):
    task_repo = TaskRepository(Task, session)
    user_repo = UserRepository(User, session)
    
    tasks, users = await asyncio.gather(
        task_repo.find(),
        user_repo.find()
    )
    return {"tasks": tasks, "users": users}
```

### 笶・DON'T: 驕主ｺｦ縺ｪ eager loading

```python
# Bad: 荳崎ｦ√↑髢｢騾｣縺ｾ縺ｧ蜿門ｾ・
tasks = await repo.find(
    options=[
        joinedload(Task.user).joinedload(User.profile),
        selectinload(Task.comments).joinedload(Comment.author),
        joinedload(Task.category).joinedload(Category.parent)
    ]
)

# Good: 蠢・ｦ√↑繧ゅ・縺縺大叙蠕・
tasks = await repo.find(
    options=[joinedload(Task.user)]
)
```

### 笨・DO: 繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ邂｡逅・

```python
# Good: 隍・焚謫堺ｽ懊ｒ繝医Λ繝ｳ繧ｶ繧ｯ繧ｷ繝ｧ繝ｳ縺ｧ縺ｾ縺ｨ繧√ｋ
async with get_async_db_session() as session:
    repo = AsyncBaseRepository(Task, session)
    
    try:
        task1 = await repo.save(Task(title="Task 1"))
        task2 = await repo.save(Task(title="Task 2"))
        # commit 縺ｯ session close 譎ゅ↓閾ｪ蜍募ｮ溯｡・
    except Exception:
        # rollback 縺ｯ閾ｪ蜍募ｮ溯｡・
        raise
```

---

## 蜷梧悄迚医→縺ｮ豈碑ｼ・

### 繧ｳ繝ｼ繝画ｯ碑ｼ・

**蜷梧悄迚・(BaseRepository)**:
```python
from repom import BaseRepository
from repom.db import db_session

with db_session() as session:
    repo = BaseRepository(Task, session)
    task = repo.get_by_id(1)
    tasks = repo.find(filters=[Task.status == 'active'])
```

**髱槫酔譛溽沿 (AsyncBaseRepository)**:
```python
from repom import AsyncBaseRepository
from repom.database import get_async_db_session

async with get_async_db_session() as session:
    repo = AsyncBaseRepository(Task, session)
    task = await repo.get_by_id(1)
    tasks = await repo.find(filters=[Task.status == 'active'])
```

### 荳ｻ縺ｪ螟画峩轤ｹ

1. `async with` 縺ｧ繧ｻ繝・す繝ｧ繝ｳ蜿門ｾ・
2. 縺吶∋縺ｦ縺ｮ繝ｪ繝昴ず繝医Μ繝｡繧ｽ繝・ラ縺ｫ `await` 縺悟ｿ・ｦ・
3. 荳ｦ陦悟・逅・・ `asyncio.gather` 縺ｧ螳溽樟

---

## 縺ｾ縺ｨ繧・

### AsyncBaseRepository 縺ｮ迚ｹ蠕ｴ

- **FastAPI 縺ｪ縺ｩ髱槫酔譛溘ヵ繝ｬ繝ｼ繝繝ｯ繝ｼ繧ｯ縺ｧ菴ｿ逕ｨ**
- 縺吶∋縺ｦ縺ｮ繝｡繧ｽ繝・ラ縺ｯ `async def` 縺ｧ `await` 縺悟ｿ・ｦ・
- **荳ｦ陦悟・逅・*: `asyncio.gather` 縺ｧ隍・焚繧ｯ繧ｨ繝ｪ繧剃ｸｦ陦悟ｮ溯｡・
- **繧ｻ繝・す繝ｧ繝ｳ邂｡逅・*: `async with` 縺ｾ縺溘・ FastAPI 縺ｮ `Depends` 縺ｧ邂｡逅・

### 讖溯・蛻･繧ｬ繧､繝・

| 讖溯・ | 繧ｬ繧､繝・| 讎りｦ・|
|------|--------|------|
| 蝓ｺ譛ｬ逧・↑ CRUD | [BaseRepository 繧ｬ繧､繝云(base_repository_guide.md) | 蜿門ｾ励・菴懈・繝ｻ譖ｴ譁ｰ繝ｻ蜑企勁 |
| 讀懃ｴ｢繝ｻ繝輔ぅ繝ｫ繧ｿ繝ｪ繝ｳ繧ｰ | [Repository 荳顔ｴ壹ぎ繧､繝云(repository_advanced_guide.md#讀懃ｴ｢縺ｨ繝輔ぅ繝ｫ繧ｿ繝ｪ繝ｳ繧ｰ) | find(), 繝壹・繧ｸ繝ｳ繧ｰ縲√た繝ｼ繝・|
| Eager Loading | [Repository 荳顔ｴ壹ぎ繧､繝云(repository_advanced_guide.md#eager-loadingn1蝠城｡後・隗｣豎ｺ) | N+1 蝠城｡後・隗｣豎ｺ縲‥efault_options |
| 繧ｫ繧ｹ繧ｿ繝繝ｪ繝昴ず繝医Μ | [Repository 荳顔ｴ壹ぎ繧､繝云(repository_advanced_guide.md#繧ｫ繧ｹ繧ｿ繝繝ｪ繝昴ず繝医Μ) | 繝薙ず繝阪せ繝ｭ繧ｸ繝・け縺ｮ邨ｱ蜷・|
| 隲也炊蜑企勁 | [SoftDelete 繧ｬ繧､繝云(repository_soft_delete_guide.md) | soft_delete, restore |
| FastAPI 邨ｱ蜷・| [FilterParams 繧ｬ繧､繝云(repository_filter_params_guide.md) | 繧ｯ繧ｨ繝ｪ繝代Λ繝｡繝ｼ繧ｿ縺ｮ蝙句ｮ牙・蜃ｦ逅・|
| 繝・せ繝・| [Testing 繧ｬ繧､繝云(../testing/testing_guide.md) | 髱槫酔譛溘ユ繧ｹ繝医・繝吶せ繝医・繝ｩ繧ｯ繝・ぅ繧ｹ |

### 髱槫酔譛溽沿縺ｮ蛻ｩ轤ｹ

笨・**鬮倅ｸｦ陦梧ｧ**: 隍・焚縺ｮ繧ｯ繧ｨ繝ｪ繧剃ｸｦ陦悟ｮ溯｡後〒縺阪ｋ  
笨・**I/O蜉ｹ邇・*: 繝・・繧ｿ繝吶・繧ｹ蠕・ｩ滉ｸｭ縺ｫ莉悶・蜃ｦ逅・ｒ螳溯｡・ 
笨・**FastAPI邨ｱ蜷・*: Depends 繝代ち繝ｼ繝ｳ縺ｧ繧ｷ繝ｼ繝繝ｬ繧ｹ縺ｫ邨ｱ蜷・ 
笨・**繧ｹ繧ｱ繝ｼ繝ｩ繝薙Μ繝・ぅ**: 螟壽焚縺ｮ蜷梧凾繝ｪ繧ｯ繧ｨ繧ｹ繝医ｒ蜉ｹ邇・噪縺ｫ蜃ｦ逅・

### 谺｡縺ｮ繧ｹ繝・ャ繝・

1. **蝓ｺ遉弱ｒ蟄ｦ縺ｶ**: [BaseRepository 繧ｬ繧､繝云(base_repository_guide.md) 縺ｧ CRUD 謫堺ｽ懊ｒ逅・ｧ｣
2. **鬮伜ｺｦ縺ｪ讀懃ｴ｢**: [Repository 荳顔ｴ壹ぎ繧､繝云(repository_advanced_guide.md) 縺ｧ讀懃ｴ｢繝代ち繝ｼ繝ｳ繧貞ｭｦ鄙・
3. **FastAPI邨ｱ蜷・*: [FilterParams 繧ｬ繧､繝云(repository_filter_params_guide.md) 縺ｧ螳溯ｷｵ逧・↑邨ｱ蜷医ｒ螳溯｣・
4. **荳ｦ陦悟・逅・*: 縺薙・繧ｬ繧､繝峨・縲御ｸｦ陦悟・逅・ヱ繧ｿ繝ｼ繝ｳ縲阪ｒ豢ｻ逕ｨ

---

**譛邨よ峩譁ｰ**: 2025-12-28  
**蟇ｾ雎｡繝舌・繧ｸ繝ｧ繝ｳ**: repom v2.0+
