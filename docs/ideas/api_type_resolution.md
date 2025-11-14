# API Type Resolution in FastAPI/Flask

## Status
- **Stage**: Idea
- **Priority**: Low
- **Complexity**: Medium
- **Created**: 2025-11-14
- **Last Updated**: 2025-11-14

## Overview

Automatically resolve repom model types when used as FastAPI/Flask response models, eliminating manual schema generation in API routes.

## Motivation

When using repom models in API frameworks:

**Current Workflow** (Manual):
```python
@app.get("/samples/{id}", response_model=Sample.get_response_schema())
def get_sample(id: int):
    return sample_repo.get_by_id(id)
```

**Desired Workflow** (Automatic):
```python
@app.get("/samples/{id}", response_model=Sample)
def get_sample(id: int) -> Sample:
    return sample_repo.get_by_id(id)
```

**Problems with Current Approach**:
- Must call `get_response_schema()` for every route
- Verbose and error-prone
- Type hints don't match actual return type
- Inconsistent with standard FastAPI patterns

**Benefits of Automatic Resolution**:
- Cleaner, more idiomatic code
- Correct type hints for IDEs
- Less boilerplate
- Standard FastAPI patterns work naturally

## Use Cases

### 1. FastAPI Integration
```python
from fastapi import FastAPI
from repom.integrations.fastapi import use_repom_models

app = FastAPI()
use_repom_models(app)  # Enable automatic resolution

@app.get("/samples/{id}", response_model=Sample)
def get_sample(id: int) -> Sample:
    return sample_repo.get_by_id(id)
# FastAPI automatically calls Sample.get_response_schema()
```

### 2. Flask Integration
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

### 3. Automatic OpenAPI Documentation
```python
# OpenAPI docs automatically generated with correct schemas
# No manual schema specification needed
@app.get("/samples/", response_model=list[Sample])
def list_samples() -> list[Sample]:
    return sample_repo.get_all()
```

## Potential Approaches

### Approach 1: FastAPI Response Model Hook
**Description**: Intercept FastAPI's response model resolution

**Pros**:
- Works with existing FastAPI patterns
- No changes to route definitions
- Transparent to developers

**Cons**:
- Requires FastAPI-specific implementation
- May conflict with FastAPI updates
- Complex integration point

**Example**:
```python
# repom/integrations/fastapi.py
from fastapi import FastAPI
from repom.base_model import BaseModel

def use_repom_models(app: FastAPI):
    original_add_api_route = app.add_api_route
    
    def wrapped_add_api_route(*args, **kwargs):
        response_model = kwargs.get('response_model')
        if response_model and issubclass(response_model, BaseModel):
            kwargs['response_model'] = response_model.get_response_schema()
        return original_add_api_route(*args, **kwargs)
    
    app.add_api_route = wrapped_add_api_route
```

### Approach 2: Custom Decorator
**Description**: Provide decorator that handles schema resolution

**Pros**:
- Explicit and clear
- Framework-agnostic
- Easy to implement

**Cons**:
- Additional decorator required
- Not standard FastAPI pattern
- More boilerplate

**Example**:
```python
from repom.integrations import repom_response

@app.get("/samples/{id}")
@repom_response(Sample)
def get_sample(id: int):
    return sample_repo.get_by_id(id)
```

### Approach 3: Response Class Wrapper
**Description**: Wrap FastAPI Response classes to handle repom models

**Pros**:
- Works with FastAPI's response system
- Can handle multiple response types
- Maintains FastAPI patterns

**Cons**:
- More complex implementation
- Requires custom Response classes

**Example**:
```python
from repom.integrations.fastapi import RepomResponse

@app.get("/samples/{id}")
def get_sample(id: int) -> RepomResponse[Sample]:
    return sample_repo.get_by_id(id)
```

## Technical Considerations

### FastAPI Integration Points
- **Route Registration**: Intercept `add_api_route()`
- **Response Model Resolution**: Hook into response model processing
- **OpenAPI Schema Generation**: Ensure schemas appear in docs
- **Type Validation**: Maintain Pydantic validation behavior

### Flask Integration Points
- **View Decorators**: Custom decorator for response schemas
- **Response Serialization**: Convert SQLAlchemy models to dicts
- **JSON Encoding**: Handle custom types (datetime, JSON fields)
- **Error Handling**: Integrate with Flask error handlers

### Compatibility Concerns
- **FastAPI Versions**: Support 0.100+ (current patterns)
- **Pydantic Versions**: Already compatible with Pydantic 2.x
- **Type Hints**: Maintain correct type hints for IDEs
- **Generic Types**: Handle `list[Sample]`, `dict[str, Sample]`, etc.

### Performance
- Schema generation is cached in `get_response_schema()`
- No additional overhead per request
- One-time resolution during route registration

### Error Handling
- Use Phase 2 error handling (SchemaGenerationError)
- Fail fast during app startup (dev mode)
- Log warnings in production
- Provide clear error messages

## Integration Points

### Affected Components
- **New Package**: `repom/integrations/` (FastAPI, Flask modules)
- `pyproject.toml` - Add optional dependencies
- `README.md` - Document integration patterns
- `repom/base_model.py` - May need integration hooks

### Example Package Structure
```
repom/integrations/
├── __init__.py
├── fastapi.py              # FastAPI integration
├── flask.py                # Flask integration (future)
└── common.py               # Shared utilities
```

### Optional Dependencies
```toml
[tool.poetry.extras]
fastapi = ["fastapi>=0.100.0"]
flask = ["flask>=2.0.0"]
all = ["fastapi>=0.100.0", "flask>=2.0.0"]
```

### Installation
```bash
# Install with FastAPI integration
poetry add repom[fastapi]

# Install with all integrations
poetry add repom[all]
```

## Next Steps

- [ ] Research FastAPI route registration internals
- [ ] Prototype Approach 1 (response model hook)
- [ ] Test with various response types (single, list, dict)
- [ ] Test with generic types (`list[Sample]`, `Optional[Sample]`)
- [ ] Verify OpenAPI documentation generation
- [ ] Test with FastAPI dependency injection
- [ ] Consider Flask integration approach
- [ ] Evaluate impact on existing projects
- [ ] Move to `docs/research/` for detailed implementation plan

## Related Documents

- `repom/base_model.py` - BaseModel with `get_response_schema()`
- `README.md` - Current usage patterns
- FastAPI documentation: [Response Model](https://fastapi.tiangolo.com/tutorial/response-model/)

## Questions to Resolve

1. Should this be a separate package (`repom-fastapi`) or integrated?
2. How to handle models with complex relationships (joins, lazy loading)?
3. Should we support FastAPI's `response_model_exclude`, `response_model_include`?
4. How to handle async vs sync repository methods?
5. Should we provide middleware for automatic model-to-dict conversion?
6. How to handle nested models and circular references?
7. Should we support FastAPI's background tasks with repom models?

## Additional Ideas

### Middleware for Automatic Conversion
Automatically convert SQLAlchemy instances to Pydantic models:
```python
from repom.integrations.fastapi import RepomMiddleware

app = FastAPI()
app.add_middleware(RepomMiddleware)

@app.get("/samples/{id}")
def get_sample(id: int):
    # Returns SQLAlchemy instance - automatically converted
    return sample_repo.get_by_id(id)
```

### Dependency Injection Helpers
Integrate repom repositories with FastAPI dependencies:
```python
from repom.integrations.fastapi import RepomDepends

@app.get("/samples/{id}")
def get_sample(
    id: int,
    repo: SampleRepository = RepomDepends()
):
    return repo.get_by_id(id)
```

### WebSocket Support
Handle repom models in WebSocket connections:
```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    sample = sample_repo.get_by_id(1)
    # Automatically serialize for WebSocket
    await websocket.send_json(sample)
```

### GraphQL Integration
Extend to Strawberry/Ariadne GraphQL:
```python
import strawberry
from repom.integrations.graphql import from_repom_model

@strawberry.type
class SampleType(from_repom_model(Sample)):
    pass
```
