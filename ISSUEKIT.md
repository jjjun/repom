# repom project profile

## Responsibilities

repom owns reusable repository-pattern and ORM utilities for Python/FastAPI
projects. It provides SQLAlchemy model bases, repository classes, async and
sync database helpers, schema generation, filtering, eager loading conventions,
soft-delete and many-to-many mixins, Alembic setup/reset helpers, config hooks
for SQLite/Postgres/Redis/pgAdmin, database test fixtures, and master-data sync
utilities. Changes belong here when they affect generic persistence behavior
used by application projects.

## Tech stack

- Python package managed with `uv`.
- SQLAlchemy and Alembic utilities.
- Package modules under `repom`.
- Tests under `tests/` with unit, behavior, and integration coverage.
- Documentation under `docs/guides`, `docs/technical`, and `docs/ideas`.

## Public surface

- Base model and repository abstractions, including async repository support.
- Automatic schema generation helpers and response field handling.
- Filter/query parameter utilities and eager loading conventions.
- Soft-delete and relationship mixins.
- Alembic setup, reset, templates, and migration helpers.
- Database config hooks for SQLite, Postgres, Redis, pgAdmin, and tests.
- Master-data sync and database test fixture helpers.

## Example in-scope requests

- "Add a repository query helper used by multiple domains."
- "Improve async repository eager loading behavior."
- "Extend automatic schema generation for SQLAlchemy models."
- "Add an Alembic helper or database test fixture."

## Example out-of-scope requests

- Application-specific API endpoints or migrations in mine-py.
- FastAPI route/decorator framework behavior owned by fast-domain.
- Generic app config/logging foundations owned by basekit.
- Browser automation and crawling owned by py_cr_wrapper.
