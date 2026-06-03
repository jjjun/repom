---
id: 79
status: completed
priority: medium
created: 2026-06-03
completed: 2026-06-03
stage: done
origin: mine-py#237@54556aa4
title: Add generic ManyToManyMixin to repom.mixins
---

# Issue #79: Add generic ManyToManyMixin to repom.mixins

## Problem

Adopted from an incoming cross-project proposal.

## Proposed Solution

# Proposal: Add generic ManyToManyMixin to repom.mixins

## Summary

Add a generic `ManyToManyMixin` to repom (target: `repom/mixins/`,
alongside the existing `soft_delete.py`). mine-py currently carries this
mixin inside a domain package, but it has no domain knowledge and is
base-layer SQLAlchemy behavior that fits repom.

## Origin

Proposed from mine-py during a pass to move base-layer logic out of
project domains and into fast-domain / repom. mine-py follow-up is tracked
in mine-py issue #237 (adopt the repom mixin and delete the local copy).

## Current code (mine-py)

Location: `src/domains/anime_shared/models/mixin/many_to_many_mixin.py`.
It manages many-to-many relations through a link table and relies only on
`sqlalchemy.orm.object_session` plus model/link classes passed as
arguments. No anime/title/domain logic.

API:

- `add_related_item(data, target_model_class, link_model_class,
  self_foreign_key, target_foreign_key, required_fields, lookup_fields)`
  - Looks up an existing target row by `lookup_fields`; if found and
    already linked, returns it; if found but unlinked, creates the link;
    otherwise creates the target row and the link. Returns the target.
- `remove_related_item(item_id, link_model_class, self_foreign_key,
  target_foreign_key)`
  - Deletes the link row matching `self.id` and `item_id`. Returns
    True/False.

Both use `object_session(self)` and `self.id`.

## Proposed change

1. Add `repom/mixins/many_to_many.py` defining `ManyToManyMixin` with the
   same two methods and signatures, so consumers can mix it into a
   `BaseModel` subclass.
2. Export it from `repom.mixins` (`__init__.py`).
3. Add unit tests under `tests/unit_tests/` covering: create-new-and-link,
   link-existing-unlinked, no-op when already linked, and remove
   (hit/miss), using a pair of throwaway models + link model.
4. Note: the `required_fields` argument is currently accepted but not
   enforced in the mine-py implementation. Please decide whether to keep
   it as a no-op for signature compatibility or validate it; mine-py can
   adapt either way.

## Compatibility

mine-py has a single consumer today (`AniVideoItemModel`). Keeping the
method names and argument order identical lets mine-py switch to the repom
import with no behavior change. If you prefer a slightly different API
(e.g. dropping unused `required_fields`), say so in the reply and mine-py
issue #237 will adapt.

## Why repom

- Generic SQLAlchemy relation management, no app/domain coupling.
- repom already owns shared model mixins (`repom/mixins/soft_delete.py`).
- Keeps the base-vs-project boundary clean per mine-py AGENTS.md.

## Local triage decisions

The proposal is sound: the mixin has no domain coupling (only
`object_session(self)`, `self.id`, and passed-in model/link classes), and
`repom/mixins/` already hosts `soft_delete.py`, so it fits repom's
framework-agnostic mandate. Adopt with the following API/quality cleanups
applied during the port:

1. Drop `required_fields`. It is accepted but never enforced in the mine-py
   implementation (dead parameter). Remove it from the signature instead of
   keeping a no-op. mine-py #237 will adapt to the trimmed signature.
2. Modernize to SQLAlchemy 2.0 style. The mine-py code uses legacy
   `session.query(...)`; rewrite lookups as `session.scalars(select(...))`
   since repom targets SQLAlchemy 2.0+.
3. Drop the unused `from sqlalchemy import Column` import.
4. Add `type[...]` hints for `target_model_class` / `link_model_class` and
   document in the docstring that `self` must be persisted/flushed (so
   `self.id` is populated) before `add_related_item` is called, and that
   commit is the caller's responsibility (consistent with `soft_delete.py`,
   though this mixin does `session.add`/`flush` internally for the link rows).

## Implementation Plan

1. Add `repom/mixins/many_to_many.py` defining `ManyToManyMixin` with the
   two methods, applying the triage decisions above:
   - `add_related_item(data, target_model_class, link_model_class,
     self_foreign_key, target_foreign_key, lookup_fields)` (no
     `required_fields`).
   - `remove_related_item(item_id, link_model_class, self_foreign_key,
     target_foreign_key)`.
2. Export `ManyToManyMixin` from `repom/mixins/__init__.py` (add to
   `__all__` and the module docstring).
3. Add unit tests under `tests/unit_tests/` with a throwaway pair of models
   plus a link model, covering: create-new-and-link, link-existing-unlinked,
   no-op when already linked, and remove (hit / miss).

## Test Plan

- `uv run pytest tests/unit_tests`
- `uv run issuekit check-encoding`

## Follow-up

- On completion, reply to the origin via `issuekit propose --reply 79` so
  mine-py #237 learns the final signature (`required_fields` dropped).

## Related Resources

- Origin: `mine-py#237@54556aa4`

## Handoff

- Summary: Added ManyToManyMixin with SQLAlchemy 2.0 select-based target/link handling, exported it from repom.mixins, and covered create/link/no-op/remove behavior with unit tests. Dropped the unused required_fields parameter per triage.
- Branch: `main`
- Commit: `15ef8edc31f810fa6abd64f0be95473bf6acfe2d`

**Completed**: 2026-06-03

## Completion Notes

- Approved by claude.
- Verification: `uv run pytest tests/unit_tests/test_many_to_many_mixin.py (5 passed); uv run pytest tests/unit_tests (915 passed, 11 skipped); uv run issuekit check-encoding passed. ManyToManyMixin added to repom/mixins/many_to_many.py and exported from repom.mixins; required_fields dropped, lookups use SQLAlchemy 2.0 select/scalars, type hints + docstring notes added.`
