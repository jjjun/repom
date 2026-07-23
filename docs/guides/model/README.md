# Model guides

- [BaseModelAuto and Pydantic schema generation](base_model_auto_guide.md)
- [System columns and custom types](system_columns_and_custom_types.md)
- [Soft delete](soft_delete_guide.md)

Application-specific models belong in the consuming project. Inherit from
`BaseModel` or `BaseModelAuto` and opt in only to the shared behavior the
application needs.
