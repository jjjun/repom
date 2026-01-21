# get_response_schema() - Technical Documentation

## Overview

`get_response_schema()` is a class method in `BaseModel` that dynamically generates Pydantic response schemas from SQLAlchemy models. It combines database column definitions with additional fields declared via the `@response_field` decorator.

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    BaseModel                                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  @response_field decorator                                  │
│    └─> Stores type metadata in method._response_fields      │
│                                                              │
│  get_response_schema()                                       │
│    ├─> Reads SQLAlchemy column definitions                  │
│    ├─> Reads @response_field metadata                       │
│    ├─> Registers fields in _EXTRA_FIELDS_REGISTRY           │
│    ├─> Generates Pydantic schema via create_model()         │
│    ├─> Calls model_rebuild() if forward_refs provided       │
│    └─> Caches schema in _response_schemas                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘

Global Storage:
  _EXTRA_FIELDS_REGISTRY: WeakKeyDictionary[type, Dict[str, Any]]
  BaseModel._response_schemas: Dict[str, Type[Any]]
```

### Data Flow

```
1. Model Definition
   ┌──────────────────────────────┐
   │ class MyModel(BaseModel):    │
   │   name = Column(String)      │
   │                              │
   │   @response_field(           │
   │     tags=List[str]           │
   │   )                          │
   │   def to_dict(self):         │
   │     ...                      │
   └──────────────────────────────┘
                ↓
2. Decorator Execution (at import time)
   ┌──────────────────────────────┐
   │ to_dict._response_fields =   │
   │   {'tags': List[str]}        │
   └──────────────────────────────┘
                ↓
3. Schema Generation (at runtime)
   ┌──────────────────────────────┐
   │ schema = MyModel.            │
   │   get_response_schema()      │
   └──────────────────────────────┘
                ↓
4. Registration (lazy, on first call)
   ┌──────────────────────────────┐
   │ _EXTRA_FIELDS_REGISTRY[cls]  │
   │   = {'tags': List[str]}      │
   └──────────────────────────────┘
                ↓
5. Pydantic Schema Creation
   ┌──────────────────────────────┐
   │ create_model(                │
   │   'MyModelResponse',         │
   │   name=(str, ...),           │
   │   tags=(List[str], ...)      │
   │ )                            │
   └──────────────────────────────┘
                ↓
6. Caching
   ┌──────────────────────────────┐
   │ _response_schemas[           │
   │   'MyModel::MyModelResponse' │
   │ ] = schema                   │
   └──────────────────────────────┘
```

## Key Components

### 1. `@response_field` Decorator

**Purpose**: Declare additional fields that appear in `to_dict()` but are not database columns.

**Implementation**:
```python
@classmethod
def response_field(cls, **fields):
    def decorator(to_dict_method: Callable):
        to_dict_method._response_fields = fields
        return to_dict_method
    return decorator
```

**Storage**: Metadata is stored as a method attribute `_response_fields`.

**Timing**: Executed at **import time** when the class is defined.

### 2. `_EXTRA_FIELDS_REGISTRY`

**Type**: `WeakKeyDictionary[type, Dict[str, Any]]`

**Purpose**: Global registry mapping model classes to their extra fields.

**Why WeakKeyDictionary?**
- Allows garbage collection of model classes
- Prevents memory leaks in long-running applications
- Automatically cleans up when model classes are no longer referenced

**Registration Timing**: 
- **Lazy** - Fields are registered when `get_response_schema()` is first called
- Not at import time, not at decorator execution time

### 3. Schema Caching

**Storage**: `BaseModel._response_schemas: Dict[str, Type[Any]]`

**Cache Key Format**:
```python
cache_key = f"{cls.__name__}::{schema_name}"
if forward_refs:
    cache_key += f"::{','.join(sorted(forward_refs.keys()))}"
```

**Examples**:
- `"MyModel::MyModelResponse"`
- `"MyModel::MyModelResponse::ChildResponse,ParentResponse"`

**Benefits**:
- Avoids recreating schemas on every request
- Significant performance improvement in API servers
- Forward refs included in key to handle different resolution contexts

## API Server Integration

### Common Pattern

```python
# FastAPI endpoint definition
from fastapi import APIRouter
from src.models.my_model import MyModel

router = APIRouter()

# Generate schema at module import time (recommended)
MyModelResponse = MyModel.get_response_schema()

@router.get("/items", response_model=MyModelResponse)
def get_items():
    items = MyModel.query.all()
    return [item.to_dict() for item in items]
```

### Timing Considerations

#### 1. **Import Time Schema Generation** (Recommended)

```python
# api/endpoints/items.py
from src.models.my_model import MyModel

# ✅ Generated once at import time
MyModelResponse = MyModel.get_response_schema()

@app.get("/items", response_model=MyModelResponse)
def get_items():
    ...
```

**Pros**:
- Schema generated once when module is imported
- Cached for all subsequent requests
- Minimal runtime overhead

**Cons**:
- Slightly slower application startup
- Import-time dependencies must be resolved

#### 2. **Lazy Schema Generation** (Not Recommended)

```python
@app.get("/items")
def get_items():
    # ❌ Generates schema on first request only (cached after)
    MyModelResponse = MyModel.get_response_schema()
    return {"response_model": MyModelResponse}
```

**Pros**:
- Faster application startup
- Defers work until needed

**Cons**:
- First request is slower
- Harder to debug import/dependency issues
- Cannot use `response_model` in decorator

#### 3. **Startup Event Generation** (Alternative)

```python
# FastAPI startup event
@app.on_event("startup")
def generate_schemas():
    # Pre-generate all schemas
    MyModel.get_response_schema()
    OtherModel.get_response_schema()
```

## Type Resolution in API Servers

### Standard Types (List, Dict, Optional)

**Current Behavior**: Automatically resolved by Pydantic.

```python
@BaseModel.response_field(
    tags=List[str],        # ✅ Works without forward_refs
    metadata=Dict[str, Any]  # ✅ Works without forward_refs
)
def to_dict(self):
    ...

# No forward_refs needed
MyResponse = MyModel.get_response_schema()
```

**Why it works**:
- `List`, `Dict`, etc. are from `typing` module
- Pydantic has built-in support for these types
- `model_rebuild()` is not required for standard types

### Custom Model References (Forward References)

**Problem**: Circular dependencies or not-yet-defined models.

```python
# models/parent.py
class Parent(BaseModel):
    @response_field(
        children=List['ChildResponse']  # ← String reference
    )
    def to_dict(self):
        ...

# api/schemas/parent.py
from models.parent import Parent
from api.schemas.child import ChildResponse  # ← Must import first

# Need to resolve the string reference
ParentResponse = Parent.get_response_schema(
    forward_refs={'ChildResponse': ChildResponse}
)
```

### Module Import Context

**Hypothesis**: In API server environments, the import context might affect type resolution.

**Potential Issues**:

1. **Circular Imports**
   ```python
   # models/a.py
   from models.b import BModel  # ← Circular dependency
   
   class AModel(BaseModel):
       @response_field(items=List['BResponse'])
       def to_dict(self): ...
   
   # models/b.py
   from models.a import AModel  # ← Circular dependency
   
   class BModel(BaseModel):
       @response_field(items=List['AResponse'])
       def to_dict(self): ...
   ```

2. **Dynamic Imports**
   ```python
   # If models are imported dynamically
   import importlib
   model_module = importlib.import_module('models.my_model')
   MyModel = model_module.MyModel
   
   # Type resolution context might be different
   schema = MyModel.get_response_schema()
   ```

3. **Hot Reload / Development Mode**
   ```python
   # In development mode with auto-reload (uvicorn --reload)
   # Modules might be reloaded, affecting type resolution
   ```

## `model_rebuild()` Behavior

### Current Implementation

```python
if forward_refs:
    try:
        schema.model_rebuild(_types_namespace=forward_refs)
    except Exception as e:
        import warnings
        warnings.warn(f"Failed to rebuild {schema_name}: {e}")
        pass
```

### What `model_rebuild()` Does

From Pydantic documentation:
> `model_rebuild()` rebuilds the model schema, optionally using a new types namespace to resolve forward references.

**Parameters**:
- `_types_namespace`: Dict mapping string type names to actual type objects

**When it's called** (in current code):
- Only if `forward_refs` parameter is provided
- Not called for standard types like `List`, `Dict`

### Namespace Resolution

**Current behavior**:
```python
# User provides forward_refs
schema.model_rebuild(_types_namespace={'ChildResponse': ChildResponse})

# Namespace contains ONLY user-provided types
# Standard types (List, Dict) are NOT in namespace
```

**Potential improvement**:
```python
import typing

# Include standard types in namespace
namespace = {
    'List': typing.List,
    'Dict': typing.Dict,
    'Optional': typing.Optional,
    'Any': typing.Any,
    **forward_refs  # User-provided types
}
schema.model_rebuild(_types_namespace=namespace)
```

## Observed Issues in API Servers

### Issue: `List` requires `forward_refs`

**Symptoms**:
```python
# This fails in some environments
MyResponse = MyModel.get_response_schema()

# This works
MyResponse = MyModel.get_response_schema(
    forward_refs={'List': List}
)
```

**Possible Causes**:

1. **Pydantic Version Differences**
   - Older Pydantic versions might have different type resolution
   - Pydantic 1.x vs 2.x have different behaviors

2. **Import Context**
   - FastAPI/Starlette import hooks might affect type resolution
   - Namespace pollution from other libraries

3. **`model_rebuild()` Side Effects**
   - If `forward_refs` is provided, `model_rebuild()` is called
   - This might trigger different type resolution logic
   - Empty `forward_refs={}` vs no parameter might behave differently

4. **Python Version**
   - `from __future__ import annotations` changes behavior
   - String annotations become default in Python 3.10+

### Investigation Recommendations

**Test in actual API environment**:
```python
# test_api_schema.py
from fastapi import FastAPI
from src.models.my_model import MyModel

app = FastAPI()

# Test 1: Import time generation
MyResponse1 = MyModel.get_response_schema()

# Test 2: With empty forward_refs
MyResponse2 = MyModel.get_response_schema(forward_refs={})

# Test 3: With List in forward_refs
from typing import List
MyResponse3 = MyModel.get_response_schema(forward_refs={'List': List})

@app.get("/test1", response_model=MyResponse1)
def test1(): ...

@app.get("/test2", response_model=MyResponse2)
def test2(): ...

@app.get("/test3", response_model=MyResponse3)
def test3(): ...

# Run: uvicorn test_api_schema:app --reload
# Check if all endpoints work
```

## Best Practices

### 1. Schema Generation Timing

✅ **DO**: Generate schemas at module import time
```python
from models.my_model import MyModel
MyResponse = MyModel.get_response_schema()
```

❌ **DON'T**: Generate schemas inside request handlers
```python
@app.get("/items")
def get_items():
    MyResponse = MyModel.get_response_schema()  # ❌ Wasteful
    ...
```

### 2. Forward References

✅ **DO**: Use forward refs only for custom models
```python
ParentResponse = Parent.get_response_schema(
    forward_refs={'ChildResponse': ChildResponse}
)
```

❌ **DON'T**: Include standard types in forward refs (usually unnecessary)
```python
# Usually not needed
MyResponse = MyModel.get_response_schema(
    forward_refs={'List': List, 'Dict': Dict}  # ❌ Redundant
)
```

### 3. Circular Dependencies

✅ **DO**: Use string annotations and resolve in schema files
```python
# models/parent.py
@response_field(children=List['ChildResponse'])  # String reference
def to_dict(self): ...

# api/schemas/parent.py
from api.schemas.child import ChildResponse
ParentResponse = Parent.get_response_schema(
    forward_refs={'ChildResponse': ChildResponse}
)
```

### 4. Cache Awareness

✅ **DO**: Be aware of caching behavior
```python
# First call - generates and caches
schema1 = MyModel.get_response_schema()

# Second call - returns cached
schema2 = MyModel.get_response_schema()

assert schema1 is schema2  # ✅ Same object
```

⚠️ **BEWARE**: Different forward_refs create different cache entries
```python
schema1 = MyModel.get_response_schema()
schema2 = MyModel.get_response_schema(forward_refs={'A': TypeA})

assert schema1 is not schema2  # ⚠️ Different cache keys
```

## Future Improvements

### 1. Always Include Standard Types in Namespace

```python
# Proposed change
if forward_refs or True:  # Always rebuild with full namespace
    import typing
    namespace = {
        'List': typing.List,
        'Dict': typing.Dict,
        'Optional': typing.Optional,
        'Any': typing.Any,
        'Set': typing.Set,
        'Tuple': typing.Tuple,
    }
    if forward_refs:
        namespace.update(forward_refs)
    
    schema.model_rebuild(_types_namespace=namespace)
```

**Benefits**:
- Eliminates need for `forward_refs={'List': List}`
- More robust across different environments
- Consistent behavior

**Risks**:
- Might affect performance (minimal)
- Might change behavior for some edge cases

### 2. Automatic Forward Reference Detection

```python
# Scan field types for string references
def _extract_forward_refs(field_type):
    """Extract all string type references from a type annotation"""
    # Handle List['MyType'], Dict[str, 'MyType'], etc.
    ...

# Auto-populate forward_refs from available models
def get_response_schema(cls, auto_resolve=True, **kwargs):
    if auto_resolve:
        # Find all imported Response classes
        # Add them to forward_refs automatically
        ...
```

### 3. Better Error Messages

```python
# Current: Silent failure with warning
warnings.warn(f"Failed to rebuild {schema_name}: {e}")

# Proposed: Detailed error with resolution hints
raise SchemaGenerationError(
    f"Failed to generate schema for {schema_name}. "
    f"Unresolved type references: {unresolved_types}. "
    f"Consider adding forward_refs={{'Type': Type}} parameter."
)
```

## Debugging

### Enable Verbose Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Add debug output to get_response_schema
schema = MyModel.get_response_schema()
```

### Inspect Registry

```python
# Check what's in the registry
extra_fields = MyModel.get_extra_fields_debug()
print(f"Extra fields: {extra_fields}")
```

### Inspect Generated Schema

```python
schema = MyModel.get_response_schema()
print(f"Schema name: {schema.__name__}")
print(f"Fields: {list(schema.model_fields.keys())}")

for name, field in schema.model_fields.items():
    print(f"  {name}: {field.annotation}")
```

### Check Cache

```python
print(f"Cached schemas: {MyModel._response_schemas.keys()}")
```

## See Also

- `repom/models/base_model_auto.py` - get_response_schema() implementation
- `tests/unit_tests/test_response_field.py` - Test cases
- Pydantic documentation: https://docs.pydantic.dev/latest/
- FastAPI with Pydantic: https://fastapi.tiangolo.com/tutorial/response-model/
