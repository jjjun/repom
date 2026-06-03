---
origin: mine-py#237@54556aa4
to: repom
reply_to:
created: 2026-06-03
title: Add generic ManyToManyMixin to repom.mixins
---

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
