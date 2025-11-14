# Schema Validation Command

## Status
- **Stage**: Idea
- **Priority**: Medium
- **Complexity**: Low
- **Created**: 2025-11-14
- **Last Updated**: 2025-11-14

## Overview

Create a CLI command to validate all model schemas at build/deployment time, catching schema generation errors before they reach production.

## Motivation

Currently, schema generation errors only occur when `get_response_schema()` is called at runtime. This means:
- Errors may not be discovered until production
- CI/CD pipelines cannot catch schema issues early
- Developers must manually test all response endpoints

A validation command would enable:
- **CI/CD Integration**: Run as part of automated testing
- **Pre-deployment Validation**: Catch issues before release
- **Development Workflow**: Quick validation during development

## Use Cases

### 1. CI/CD Pipeline
```yaml
# .github/workflows/test.yml
- name: Validate Model Schemas
  run: poetry run repom validate-schemas
```

### 2. Pre-commit Hook
```bash
# .git/hooks/pre-commit
poetry run repom validate-schemas || exit 1
```

### 3. Development Workflow
```bash
# Quick validation during development
poetry run repom validate-schemas
# ✓ All schemas validated successfully (15 models)
```

## Potential Approaches

### Approach 1: Scan and Validate
**Description**: Auto-discover all BaseModel subclasses and call `get_response_schema()`

**Pros**:
- Comprehensive validation
- No manual configuration
- Catches all schema errors

**Cons**:
- May discover models not intended for responses
- Requires model imports (side effects?)

**Example**:
```python
# repom/scripts/validate_schemas.py
def validate_all_schemas():
    models = discover_base_models()  # Scan all BaseModel subclasses
    for model_cls in models:
        try:
            model_cls.get_response_schema()
            print(f"✓ {model_cls.__name__}")
        except SchemaGenerationError as e:
            print(f"✗ {model_cls.__name__}: {e}")
            return False
    return True
```

### Approach 2: Explicit Registration
**Description**: Require models to be registered for validation

**Pros**:
- Explicit control over what's validated
- No unexpected side effects
- Clear intent

**Cons**:
- Manual registration required
- May miss models

**Example**:
```python
# In model files
@register_for_validation
class MyModel(BaseModel):
    pass
```

### Approach 3: Configuration File
**Description**: List models to validate in a configuration file

**Pros**:
- Centralized configuration
- Easy to include/exclude models
- No code changes needed

**Cons**:
- Additional configuration to maintain
- May become outdated

**Example**:
```yaml
# repom.validation.yml
models:
  - repom.models.sample.Sample
  - repom.models.user_session.UserSession
```

## Technical Considerations

### Implementation
- Use existing `get_response_schema()` method
- Leverage Phase 2 error handling (dev environment behavior)
- Report all errors, not just the first one
- Provide summary statistics

### Performance
- Schema generation may be slow for large models
- Consider parallel validation for multiple models
- Cache results if possible

### Dependencies
- No new dependencies required
- Uses existing repom infrastructure
- Compatible with Poetry scripts

### Output Format
- Console output with colors (✓/✗)
- JSON format option for CI/CD parsing
- Exit code: 0 (success) or 1 (failure)

## Integration Points

### Affected Components
- `repom/scripts/` - New script: `validate_schemas.py`
- `pyproject.toml` - Add Poetry script entry point
- `README.md` - Document new command

### Interaction with Existing Features
- Uses `BaseModel.get_response_schema()`
- Leverages Phase 2 error detection
- Compatible with EXEC_ENV environment variable

### Example Output
```
$ poetry run repom validate-schemas

Validating model schemas...

✓ Sample (repom.models.sample)
✗ UserSession (repom.models.user_session)
  Error: Type 'SessionData' is not defined
  Suggestion: Add 'from typing import ForwardRef' and define type
  
✓ Product (myapp.models.product)
✗ Order (myapp.models.order)
  Error: Type 'OrderItem' is not defined
  Suggestion: Import OrderItem or use string literal 'OrderItem'

Summary: 2/4 models validated successfully
Exit code: 1
```

## Next Steps

- [ ] Research auto-discovery mechanisms (inspect, pkgutil)
- [ ] Prototype Approach 1 (scan and validate)
- [ ] Test with repom's own models
- [ ] Design CLI interface and output format
- [ ] Consider JSON output option for CI/CD
- [ ] Evaluate performance with large model sets
- [ ] Move to `docs/research/` for detailed implementation plan

## Related Documents

- `docs/issue/completed/get_response_schema_forward_refs_improvement.md` - Phase 2 error handling
- `README.md` - Phase 2 implementation details
- `repom/base_model.py` - BaseModel implementation with error handling

## Questions to Resolve

1. Should validation respect EXEC_ENV (dev/prod behavior)?
2. How to handle models in consuming projects vs. repom package?
3. Should validation run automatically in test suite?
4. What about models with complex dependencies or database connections?
5. Should we validate only response schemas, or all Pydantic schemas?
