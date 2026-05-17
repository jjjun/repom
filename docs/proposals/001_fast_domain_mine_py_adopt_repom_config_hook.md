# Proposal #001: fast-domain / mine-py adopt repom config hook base

## Metadata

| Item | Value |
|------|---|
| **ID** | 001 |
| **Target projects/packages** | fast-domain, mine-py |
| **Type** | breaking / refactor |
| **Status** | draft |
| **Created** | 2026-05-18 |
| **Last updated** | 2026-05-18 |

## Background

`repom._.config_hook` now owns the shared `Config` base class, log path
properties, empty-path skipping, and fail-fast `CONFIG_HOOK` loading behavior.

fast-domain and mine-py still have local or copied config hook implementations.
Leaving those copies in place would keep the config behavior split across
packages and would make future fixes drift again.

## Current State

- fast-domain has `fast_domain._.config_hook.Config` and imports it from
  `src/fast_domain/config.py`.
- mine-py has `src/_/ConfigHook.py`, and several subpackages import
  `from _.ConfigHook import Config, get_config_from_hook`.
- mine-py `src/mine_py/config_hook.py` calls `config.init()` inside the hook,
  while repom and fast-domain config modules call `config.init()` after applying
  the hook.

## Proposal

fast-domain should switch `FastDomainConfig` to inherit from
`repom._.config_hook.Config` and remove the local `fast_domain._.config_hook`
copy after updating imports and tests.

mine-py should choose one of these migration paths:

- Prefer direct use of `repom._.config_hook` in packages that already depend on
  repom.
- For packages that must not depend on repom, keep a local compatibility shim
  but synchronize its behavior with repom.

mine-py should also remove `config.init()` from the central hook and leave init
responsibility in each package's `config.py` module, preventing double init when
repom or fast-domain apply the hook.

## Expected Effect

- Invalid `CONFIG_HOOK` paths fail at startup instead of being silently ignored.
- `log_path`, `log_file`, and `log_file_path` behavior is consistently
  available from the shared config base.
- Future config hook fixes can be made in repom first and adopted by consumers
  without maintaining independent copies.

## repom Follow-up

- Keep `ConfigHookLoadError` importable from `repom._.config_hook`.
- Keep config hook unit tests covering missing module, missing function, and
  non-callable hook targets.
- Remove this proposal after fast-domain and mine-py have completed or rejected
  the migration.

## Related Files

- `repom/_/config_hook.py`
- `tests/unit_tests/test_config_hook.py`
- `README.md`
- `C:\Users\jj\Desktop\workspace_main\projects\fast-domain\docs\issues\active\137_consolidate_config_base_class_into_repom.md`
- `C:\Users\jj\Desktop\workspace_main\projects\mine-py\src\_\ConfigHook.py`
- `C:\Users\jj\Desktop\workspace_main\projects\mine-py\src\mine_py\config_hook.py`
