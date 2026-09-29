# Hybrid package logging: history

## Decision

Generic logging handlers and configuration belong to `basekit.logging`.
repom keeps its logging integration for the `repom` namespace and
`RepomConfig`.

## Rationale

Sharing handler setup avoids maintaining the same behavior in multiple
packages. Keeping repom's integration lets applications use their standard
logging configuration while retaining repom-specific defaults. Current usage
is documented in the [logging guide](../guides/features/logging_guide.md).
