# Issue #001: FastAPI Depends Compatibility Fix

## Status
- **Created**: 2025-12-25
- **Completed**: 2025-12-25
- **Priority**: High
- **Complexity**: Medium

## Problem Description

`@contextmanager` and `@asynccontextmanager` decorators on `get_db_session()`, `get_db_transaction()`, `get_async_db_session()`, and `get_async_db_transaction()` broke FastAPI Depends compatibility.

**Root Cause**: 
- The decorators convert generator functions to context manager objects
- FastAPI Depends requires the generator protocol (`next()`/`__anext__()`), NOT context manager protocol
- `inspect.isgeneratorfunction()` returns `False` when `@contextmanager` is applied
- Resulted in `AttributeError: '_GeneratorContextManager' object has no attribute 'throw'`

## Expected Behavior

These functions should work as FastAPI dependencies:

```python
from fastapi import Depends
from repom.database import get_db_session

@app.get("/items")
def get_items(db: Session = Depends(get_db_session)):
    # Should work without errors
    return db.query(Item).all()
```

## Actual Behavior (Before Fix)

```python
# FastAPI raised AttributeError when using with Depends
AttributeError: '_GeneratorContextManager' object has no attribute 'throw'
```

## Solution

### Changes Made

1. **Removed decorators from public API** ([repom/database.py](repom/database.py)):
   - Line 465: Removed `@contextmanager` from `get_db_session()`
   - Line 486: Removed `@contextmanager` from `get_db_transaction()`
   - Line 536: Removed `@asynccontextmanager` from `get_async_db_session()`
   - Line 558: Removed `@asynccontextmanager` from `get_async_db_transaction()`

2. **Kept decorators for internal methods**:
   - `DatabaseManager.get_sync_session()` - still uses `@contextmanager`
   - `DatabaseManager.get_async_session()` - still uses `@asynccontextmanager`
   - These internal methods need context manager protocol for 'with' statement usage

3. **Updated tests**:
   - Added 17 new FastAPI Depends tests (15 passed, 2 skipped)
   - Replaced old 'with' statement tests with deprecation placeholders
   - Tests verify generator protocol using `next()`/`__anext__()` instead of 'with'

4. **Added dev dependencies**:
   - `fastapi` - For integration testing
   - `httpx` - For async client testing

### Migration Guide

**OLD (No longer works):**
```python
# This will raise AttributeError
with get_db_session() as db:
    db.query(Model).all()
```

**NEW (FastAPI Depends):**
```python
from fastapi import Depends
from repom.database import get_db_session

@app.get("/items")
def get_items(db: Session = Depends(get_db_session)):
    return db.query(Model).all()
```

**Alternative (Context Manager):**
```python
from repom.database import _db_manager

# Use DatabaseManager directly for 'with' statement
with _db_manager.get_sync_session() as db:
    db.query(Model).all()
```

## Test Results

### FastAPI Depends Tests (All Passing)
```
tests/unit_tests/test_database.py::TestFastAPIDependsPattern
  ✅ test_get_db_session_is_generator_function
  ✅ test_get_db_session_returns_generator
  ✅ test_get_db_session_yields_session_via_next
  ⏭️  test_get_db_session_context_manager_compatibility (expected skip)
  ✅ test_get_db_transaction_is_generator_function
  ✅ test_get_db_transaction_returns_generator
  ✅ test_get_db_transaction_yields_session_via_next
  ✅ test_fastapi_depends_real_simulation

tests/unit_tests/test_async_database.py::TestFastAPIDependsPattern
  ✅ test_get_async_db_session_is_async_generator_function
  ✅ test_get_async_db_session_returns_async_generator
  ✅ test_get_async_db_session_yields_session_via_anext
  ⏭️  test_get_async_db_session_context_manager_compatibility (expected skip)
  ✅ test_get_async_db_transaction_is_async_generator_function
  ✅ test_get_async_db_transaction_returns_async_generator
  ✅ test_get_async_db_transaction_yields_session_via_anext
  ✅ test_fastapi_depends_real_simulation
  ✅ test_session_has_required_methods

Result: 15 passed, 2 skipped
```

### Full Test Suite
```
Total: 322 passed, 9 skipped, 1 unrelated failure (Unicode encoding)
Time: ~3 seconds
```

## Breaking Changes

⚠️ **BREAKING CHANGE**: `get_db_session()`, `get_db_transaction()`, `get_async_db_session()`, and `get_async_db_transaction()` no longer support 'with' statement usage.

**What to do:**
1. **FastAPI users**: No action needed - Depends will now work correctly
2. **Direct 'with' statement users**: Switch to `_db_manager.get_sync_session()` or `_db_manager.get_async_session()`

## Related Documents

- **Proof of Concept**: test_contextmanager_behavior.py (removed after verification)
- **Integration Test**: test_fastapi_depends.py (removed after verification)
- **Final Tests**: [tests/unit_tests/test_database.py](tests/unit_tests/test_database.py), [tests/unit_tests/test_async_database.py](tests/unit_tests/test_async_database.py)

## Commits

- Initial failing tests: `8eeaa04` (2025-12-25)
- Fix implementation: `3285597` (2025-12-25)

## Technical Details

### Why @contextmanager Breaks FastAPI Depends

```python
from contextlib import contextmanager
import inspect

# WITHOUT @contextmanager
def my_generator():
    yield "value"

print(inspect.isgeneratorfunction(my_generator))  # True
gen = my_generator()
print(type(gen))  # <class 'generator'>
print(hasattr(gen, '__next__'))  # True ✅

# WITH @contextmanager
@contextmanager
def my_context_manager():
    yield "value"

print(inspect.isgeneratorfunction(my_context_manager))  # False ❌
cm = my_context_manager()
print(type(cm))  # <class 'contextlib._GeneratorContextManager'>
print(hasattr(cm, '__next__'))  # False ❌
print(hasattr(cm, '__enter__'))  # True (but FastAPI doesn't use this)
```

FastAPI Depends calls:
1. `inspect.isgeneratorfunction()` - must return True
2. `next(generator)` - must work to get yielded value

With `@contextmanager`, both fail.

## Lessons Learned

1. **Decorators can fundamentally change function type** - `@contextmanager` converts generators to context managers
2. **Tests must match real usage** - Our old tests used 'with' statement, not the `next()` pattern FastAPI uses
3. **Documentation must be verified** - Previous docs incorrectly claimed decorators allowed both usages
4. **Test-first approach prevents regressions** - Writing failing tests first ensured comprehensive coverage

## Next Steps

- [x] Remove `@contextmanager`/`@asynccontextmanager` decorators
- [x] Update tests to use generator protocol
- [x] Verify FastAPI Depends compatibility
- [ ] Update documentation (repository_session_patterns.md)
- [ ] Notify mine-py project that issue is resolved
