# Repository guides

These guides cover the synchronous and asynchronous repository APIs, query
construction, and transaction ownership.

## Start here

- [BaseRepository](base_repository_guide.md)
- [AsyncBaseRepository](async_repository_guide.md)
- [Session and transaction patterns](repository_session_patterns.md)

## Querying

- [Advanced queries](repository_advanced_guide.md)
- [`order_by`](order_by_guide.md)
- [`FilterParams`](repository_filter_params_guide.md)

## Related behavior

- [Soft delete](../model/soft_delete_guide.md)

Application repositories should subclass `BaseRepository` or
`AsyncBaseRepository` with their domain model. Keep application-specific
queries in the consuming project.
