"""Redis Docker management and configuration module."""

from repom.redis.config import RedisConfig, RedisContainerConfig


def __getattr__(name: str):
    if name in {
        "generate",
        "start",
        "stop",
        "remove",
        "get_compose_dir",
        "get_init_dir",
        "RedisManager",
    }:
        from repom.redis import manage

        return getattr(manage, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "RedisConfig",
    "RedisContainerConfig",
    "generate",
    "start",
    "stop",
    "remove",
    "get_compose_dir",
    "get_init_dir",
    "RedisManager",
]
