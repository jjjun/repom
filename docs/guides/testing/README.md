# Testing guides

- [Testing strategy and reusable fixtures](testing_guide.md)
- [Fixture details and examples](fixture_guide.md)

The shared fixtures use transaction rollback for isolation. Prefer the models
under [`tests/fixtures/models`](../../../tests/fixtures/models) for ordinary
repository tests, and keep application-specific test models in the consuming
project.

```bash
uv run pytest
uv run pytest tests/unit_tests
uv run pytest tests/behavior_tests
uv run pytest tests/integration_tests
```
