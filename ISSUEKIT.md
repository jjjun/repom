# repom project profile

## Responsibilities

repom provides reusable SQLAlchemy foundations for consuming Python
applications: model bases, synchronous and asynchronous repositories, database
session helpers, ORM mixins and custom types, Alembic integration, database
testing fixtures, and master-data utilities. It also provides project-level
database configuration and PostgreSQL, Redis, and SQLite management that
applications can adapt to their own domains.

Changes belong here when they improve generic persistence behavior shared by
applications. Application models, repositories, API endpoints, and migrations
remain in the consuming project.

## Tech stack

- Python package managed with `uv` and built with hatchling.
- SQLAlchemy 2.x and Alembic.
- `basekit` provides shared config, discovery, logging, and Docker foundations.
- Tests under `tests/` cover unit, behavior, and integration scenarios.
- Documentation under `docs/guides`, `docs/technical`, and `docs/ideas`.

## Public surface

- Base model and synchronous / asynchronous repository abstractions.
- Shared query helpers, soft-delete and relationship mixins, and custom types.
- Database configuration, session and transaction helpers, and backend hooks.
- Alembic setup helpers, templates, and shared migration environment support.
- Database test fixture factories, model discovery utilities, and master-data
  synchronization helpers.
- PostgreSQL, Redis, and SQLite configuration and management helpers.

## Example in-scope requests

- "Add a repository query helper used by multiple domains."
- "Improve async repository eager loading behavior."
- "Add a reusable SQLAlchemy mixin or custom type."
- "Add an Alembic helper or database test fixture."

## Example out-of-scope requests

- Application-specific models, repositories, API endpoints, or migrations in
  mine-py.
- Pydantic schema generation and FastAPI query dependencies, owned by
  `fast_domain.repom` in fast-domain.
- FastAPI route and decorator behavior owned by fast-domain.
- Generic config, discovery, logging, and Docker foundations owned by basekit.
- Browser automation and crawling owned by py_cr_wrapper.
