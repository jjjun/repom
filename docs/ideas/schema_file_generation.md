# Schema File Generation

## Status
- **Stage**: Idea
- **Priority**: Low
- **Complexity**: Low
- **Created**: 2025-11-14
- **Last Updated**: 2025-11-14

## Overview

Generate JSON Schema files from repom models to support API documentation tools, contract testing, and frontend TypeScript generation.

## Motivation

When building APIs with repom models, developers often need:
- **OpenAPI/Swagger Documentation**: JSON schemas for API specs
- **Frontend Types**: Generate TypeScript interfaces from schemas
- **Contract Testing**: Validate API responses against schemas
- **External Integration**: Share schemas with non-Python services

Currently:
- Schemas exist only in Python code
- Must manually create JSON Schema files
- No automated sync between models and schemas

With schema file generation:
- Automatically export schemas to files
- Keep documentation in sync with models
- Enable tooling integration (OpenAPI, TypeScript generators)

## Use Cases

### 1. OpenAPI Documentation
```bash
# Generate schemas for API documentation
poetry run repom generate-schemas --output schemas/

# Use in OpenAPI spec
# openapi.yml references schemas/Sample.json
```

### 2. Frontend TypeScript Generation
```bash
# Generate schemas
poetry run repom generate-schemas --output schemas/

# Convert to TypeScript
npx json-schema-to-typescript schemas/*.json --output src/types/
```

### 3. Contract Testing
```python
# Validate API responses against generated schemas
import json
from jsonschema import validate

with open('schemas/Sample.json') as f:
    schema = json.load(f)
    
validate(api_response, schema)  # Ensure response matches model
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

## Technical Considerations

### Custom Type Handling
repom uses custom TypeDecorators that may not serialize well:
- `ISO8601DateTime` → Should export as ISO 8601 string format
- `JSONEncoded` → Should export as object type
- `ListJSON` → Should export as array type
- `CreatedAt` → Should export as datetime string

**Solution**: Add custom serialization rules for each TypeDecorator

### File Organization
```
schemas/
├── Sample.json                 # Individual model schemas
├── UserSession.json
├── combined.json              # All schemas in one file (optional)
└── openapi/                   # OpenAPI-specific format (optional)
    └── components.yml
```

### Schema Format Options
- **JSON Schema Draft 7/2020**: Standard format
- **OpenAPI 3.0/3.1**: API-specific format
- **TypeScript**: Direct TS interface generation

### Dependencies
- **jsonschema**: Validation and schema manipulation
- **pyyaml** (optional): YAML output format
- No additional heavy dependencies

## Integration Points

### Affected Components
- `repom/scripts/` - New script: `generate_schemas.py`
- `pyproject.toml` - Add Poetry script entry point
- `repom/base_model.py` - Potential schema serialization helpers
- `README.md` - Document new command

### Interaction with Existing Features
- Uses `BaseModel.get_response_schema()`
- Compatible with Phase 2 error handling
- Works with all repom custom types

### Example Command
```bash
# Generate all schemas
poetry run repom generate-schemas

# Generate specific models
poetry run repom generate-schemas Sample UserSession

# Specify output directory
poetry run repom generate-schemas --output ./api/schemas/

# Different format
poetry run repom generate-schemas --format openapi-yaml
```

### Example Output
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

## Next Steps

- [ ] Research Pydantic's `model_json_schema()` output format
- [ ] Test with repom's custom TypeDecorators
- [ ] Prototype basic schema generation
- [ ] Evaluate need for custom serialization
- [ ] Design CLI interface (arguments, output format)
- [ ] Test with OpenAPI tools and TypeScript generators
- [ ] Consider watch mode for automatic regeneration
- [ ] Move to `docs/research/` if implementing

## Related Documents

- `repom/custom_types/` - Custom type implementations
- `README.md` - BaseModel documentation
- Pydantic documentation: [JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/)

## Questions to Resolve

1. Should schemas be committed to version control?
2. What's the best format for consuming projects (JSON vs YAML)?
3. Should we support incremental generation (only changed models)?
4. How to handle relationships between models (foreign keys)?
5. Should we include database-specific metadata (table names, indexes)?
6. Should schemas include validation rules (min/max, patterns)?
7. How to handle models with circular references?

## Additional Ideas

### Schema Versioning
Track schema versions for API compatibility:
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Sample",
  "version": "1.0.0",
  "deprecated": false,
  "properties": { ... }
}
```

### Documentation Integration
Generate markdown documentation from schemas:
```bash
poetry run repom generate-docs --from-schemas
```

### Watch Mode
Automatically regenerate schemas on file changes:
```bash
poetry run repom generate-schemas --watch
```
