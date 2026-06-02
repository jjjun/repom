---
id: 78
status: in_progress
priority: high
created: 2026-06-02
completed: 
assignee: codex
stage: implementing
implementer: codex
title: Add reusable custom-format pg_dump/pg_restore primitives with docker/host fallback
---

# Issue #78: Add reusable custom-format pg_dump/pg_restore primitives with docker/host fallback

## Problem

repom owns the "prefer the managed Docker container, fall back to host tools"
selection for PostgreSQL client tools via
`run_postgres_via_docker_or_host` in
[repom/scripts/_backup_utils.py](../../../repom/scripts/_backup_utils.py).
But this only serves the operational backup form (plain SQL piped to gzip,
restored with `gunzip` + `psql`, artifact `db_*.sql.gz`). See
[db_backup.py](../../../repom/scripts/db_backup.py) and
[db_restore.py](../../../repom/scripts/db_restore.py).

There is no repom primitive for the custom-format migration bundle
(`pg_dump --format=custom` produces `db.dump`, restored with `pg_restore`).
Downstream `mine-data` therefore hand-builds host-only `pg_dump` / `pg_restore`
commands and gates restore on `shutil.which("pg_restore")`. During the real
mine-py production migration (Windows -> pike3) this failed because neither host
had compatible PostgreSQL 16 client tools on PATH, even though the managed
container (`postgres:16-alpine`) shipped matching `pg_dump` / `pg_restore`. The
migration only succeeded after manually routing dump/restore through the
container.

This is the repom side of mine-py proposal #065 (mine-py issue #236). PostgreSQL
client selection should live in one place (repom), not be duplicated per
consumer.

## Proposed Solution

Add a focused module `repom/scripts/pg_dump_tools.py` exposing reusable
custom-format dump/restore primitives that own docker-or-host tool selection.
The module is framework-agnostic and takes explicit connection params so any
consumer can use it without importing repom's global config.

API shape:

```python
@dataclass(frozen=True)
class PgConnParams:
    host: str
    port: int
    user: str
    password: str | None
    database: str
    container_name: str | None = None

    @classmethod
    def from_config(cls) -> "PgConnParams":
        # build from repom.config.config.postgres (+ get_container_name())

@dataclass(frozen=True)
class PgToolResult:
    returncode: int
    used_docker: bool
    tool_version: str | None
    stderr: str  # password-safe; never echoes PGPASSWORD or process env

def pg_dump_custom(params: PgConnParams, dump_path: Path) -> PgToolResult: ...
def pg_restore_custom(params: PgConnParams, dump_path: Path) -> PgToolResult: ...
def pg_tools_available(params: PgConnParams) -> bool: ...
```

Behavior:

- Reuse the existing docker-or-host selection so the warning on host fallback is
  preserved. The current `run_postgres_via_docker_or_host` reads the container
  name from global config and discards callback return values; generalize it to
  (a) accept an optional `container_name` argument (defaulting to config) and
  (b) return the chosen callback's value. Existing callers that return `None`
  stay unchanged.
- `pg_dump_custom`:
  - docker path: run `pg_dump --format=custom ...` WITHOUT `--file`, capture
    binary stdout via `DockerCommandExecutor.exec_command(capture_output=True)`,
    write bytes to the host `dump_path`, fail clearly if stdout is empty.
  - host path: run host `pg_dump --format=custom --file <dump_path> ...`.
- `pg_restore_custom`:
  - docker path: stream the dump bytes to `pg_restore` over
    `DockerCommandExecutor.exec_command(stdin=<bytes>)` (adds `docker exec -i`);
    the container cannot read a host file path.
  - host path: run host `pg_restore <dump_path> ...`.
- Preserve the exact flag set mine-data relies on. Inspect mine-data's current
  `build_pg_dump_command` / `build_pg_restore_command` and mirror them
  (`--clean --if-exists --no-owner --no-acl`), placing clean/if-exists on the
  `pg_restore` side and no-owner/no-acl where mine-data currently places them.
- Keep `PGPASSWORD` in the environment only, never in argv. Ensure errors and
  `PgToolResult.stderr` never include process env, so the password cannot leak
  to logs.
- Capture the chosen tool's version (`pg_dump --version` / `pg_restore
  --version`, in-container for the docker path) for `tool_version`, and when
  stderr indicates a server/client version mismatch, add an actionable hint
  (this surfaces the DaVinci-Resolve-13.4-on-PATH class of failure as a clear
  message instead of a raw mismatch error).
- `pg_tools_available` returns True when the container is running OR host
  `pg_dump`/`pg_restore` exist, so consumers can run preflight without assuming
  host binaries.

Scope boundaries (kept out of repom): asset archive/manifest ownership and
runtime DB connection-string config stay in mine-data. repom's own
`db_backup` / `db_restore` keep using the plain-SQL `.sql.gz` path; rewiring
them onto these primitives is out of scope for this issue.

## Impact

- New module: `repom/scripts/pg_dump_tools.py`
- Modified: `repom/scripts/_backup_utils.py` (`run_postgres_via_docker_or_host`
  gains an optional `container_name` arg and returns the callback value)
- New tests: `tests/unit_tests/`
- Downstream: unblocks mine-py issue #236 / proposal #065 (mine-data swaps its
  host-only commands and `shutil.which` preflight for these primitives)

## Implementation Plan

1. Inspect mine-data `build_pg_dump_command` / `build_pg_restore_command` to
   capture the exact flags and argument order to preserve.
2. Generalize `run_postgres_via_docker_or_host` to accept an optional
   `container_name` and return the chosen callback's value; keep current
   callers working unchanged.
3. Add `repom/scripts/pg_dump_tools.py` with `PgConnParams` (+ `from_config`),
   `PgToolResult`, `pg_dump_custom`, `pg_restore_custom`, `pg_tools_available`.
4. Implement docker dump (no `--file`, capture stdout -> file, empty-stdout
   guard) and host dump (`--file`).
5. Implement docker restore (stream bytes via `exec_command(stdin=...)`) and
   host restore (`pg_restore <dump_path>`).
6. Add tool-version capture and the server/client mismatch hint; ensure stderr
   and exceptions never include process env.
7. Add unit tests with `DockerCommandExecutor` and `subprocess` mocked.

## Test Plan

- `uv run pytest tests/unit_tests` passes.
- Unit cases:
  - container running: docker path used, command has no `--file`, captured
    stdout written to dump file.
  - container stopped: host path used, command includes `--file`.
  - restore docker path: dump bytes streamed via `exec_command(stdin=...)`.
  - `pg_tools_available` True when only the container is available.
  - `PgToolResult.stderr` and raised errors never contain the password/env.
- `uv run issuekit check-encoding` passes (ASCII/LF, no BOM).

## Related Resources

- mine-py proposal #065 (`mine-py/docs/proposals/065_repom_pg_dump_restore_primitives.md`)
- mine-py issue #236 (`mine_data_docker_pg_dump_restore`)
- [repom/scripts/_backup_utils.py](../../../repom/scripts/_backup_utils.py)
- [repom/scripts/db_backup.py](../../../repom/scripts/db_backup.py)
- [repom/scripts/db_restore.py](../../../repom/scripts/db_restore.py)
- Related completed issues: #49 (docker-based pg_dump/pg_restore), #70 (unify
  docker/host fallback pattern)
- basekit: `basekit/docker_manager.py`
  (`DockerCommandExecutor.exec_command`, `is_container_running`)
