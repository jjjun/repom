# Alembic revision location: historical limitation and current contract

## Current contract

`alembic.ini` is the only source of truth for revision locations. Both
revision creation and migration execution read `version_locations` from that
file.

For a consumer that reuses repom's migration environment:

```ini
[alembic]
script_location = submod/repom/alembic
version_locations = %(here)s/alembic/versions
```

`%(here)s` resolves to the directory containing the consumer's
`alembic.ini`. A portable test fixture can use a relative `script_location` as
well.

## Why the old approach was removed

An earlier design tried to place a migration path on `RepomConfig` and pass it
to Alembic's runtime `context.configure(...)` call. That affects migration
execution after the environment has loaded, but the `alembic revision`
command chooses its output directory earlier from the Alembic configuration.
Creation and execution could therefore disagree.

The private config attribute and the runtime override were removed. Do not
reintroduce them through `CONFIG_HOOK`; configure the path in `alembic.ini`.

## Verification

The portable consumer fixture is under
[`tests/integration_tests/mock_external_project`](../../tests/integration_tests/mock_external_project).
Its diagnostic script resolves both paths and checks them against the current
checkout.

Useful upstream references:

- [Alembic configuration tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html#editing-the-ini-file)
- [Multiple version directories](https://alembic.sqlalchemy.org/en/latest/branches.html#working-with-multiple-bases)
- [Runtime environment API](https://alembic.sqlalchemy.org/en/latest/api/runtime.html)
