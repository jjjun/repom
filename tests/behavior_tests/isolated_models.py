from sqlalchemy.orm import registry


behavior_registry = registry()
Base = behavior_registry.generate_base()


def clear_behavior_models() -> None:
    behavior_registry.dispose(cascade=True)
