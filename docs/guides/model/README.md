# Model guides

- [System columns and custom types](system_columns_and_custom_types.md)
- [Soft delete](soft_delete_guide.md)

Application-specific models belong in the consuming project. Inherit from
`BaseModel` and opt in only to the shared behavior the application needs.
Pydantic schema generation for FastAPI now lives in the consuming framework.
