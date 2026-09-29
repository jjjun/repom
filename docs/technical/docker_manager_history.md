# Docker manager: history

## Decision

The generic Docker manager and command execution foundation moved to
`basekit.docker_manager` so
shared lifecycle behavior has one owner. repom keeps the service-specific
PostgreSQL and Redis managers: [`PostgresManager`](../../repom/postgres/manage.py),
[`RedisManager`](../../repom/redis/manage.py), and the shared lifecycle helper
in [`repom.docker_service`](../../repom/docker_service.py).

## Current usage

See the [Docker manager guide](../guides/features/docker_manager_guide.md) for
repom's current service commands and lifecycle helpers.
