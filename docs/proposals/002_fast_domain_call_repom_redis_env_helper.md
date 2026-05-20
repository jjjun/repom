# Proposal #002: fast-domain should call repom Redis env helper

## Metadata

| Item | Value |
|------|---|
| ID | 002 |
| Target project / package | fast-domain |
| Type | migration |
| Status | draft |
| Created | 2026-05-20 |
| Updated | 2026-05-20 |

---

## Background

repom now owns Redis environment override handling through
`repom.config_hooks.redis.apply_redis_env_overrides()`. The helper applies the
existing `REDIS_PORT` environment variable to `config.redis.port` after
`CONFIG_HOOK` runs in repom standalone usage.

fast-domain already uses a `CONFIG_HOOK` to set its Redis defaults. To preserve
the same ordering explicitly inside fast-domain's own hook policy, fast-domain
should call the repom helper at the end of its hook after setting the local
default Redis port.

---

## Current State And Problem

repom can expose the helper and keep `REDIS_PORT` working for the module-level
`repom.config.config` singleton, but it cannot edit fast-domain's
`src/fast_domain/config_hook.py` from this repository.

Until fast-domain imports and calls the helper, fast-domain's config hook does
not document that `REDIS_PORT` is intentionally applied after the hard-coded
default such as `config.redis.port = 6381`.

---

## Proposed Change

Update fast-domain's config hook:

```python
from repom.config_hooks.redis import apply_redis_env_overrides


def hook_config(config):
    config.redis.port = 6381
    apply_redis_env_overrides(config)
    return config
```

Update fast-domain docs that describe config hook environment override helpers
to include `REDIS_PORT -> config.redis.port`.

---

## Expected Effect

fast-domain keeps its project-specific Redis default while allowing the shared
repom `REDIS_PORT` override to win when explicitly set. Redis env override
ownership stays in repom instead of being duplicated downstream.

---

## repom Follow-Up

- [x] Add `repom.config_hooks.redis.apply_redis_env_overrides()`
- [x] Remove `RepomConfig.redis_port`; use `config.redis.port`
- [x] Apply the helper after `CONFIG_HOOK` in `repom.config`
- [x] Document the helper in repom guides
- [ ] Delete this proposal after fast-domain adopts or rejects the change

---

## Related Files

- `repom/config_hooks/redis.py`
- `repom/config.py`
- `docs/guides/features/config_hook_guide.md`
- `docs/guides/redis/redis_manager_guide.md`
- fast-domain: `src/fast_domain/config_hook.py`
- fast-domain: `docs/guides/config_hook.md`

---

## Discussion Log

### 2026-05-20 - repom

- fast-domain proposal #034 requested moving Redis env override handling into
  repom.
- repom implemented the shared helper and preserved standalone `REDIS_PORT`
  behavior.
- fast-domain still needs a follow-up hook/doc update.

---

## Decision

Pending fast-domain follow-up.
