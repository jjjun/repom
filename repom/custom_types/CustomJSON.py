from typing import Any, Callable, Optional

from sqlalchemy.types import JSON, TypeDecorator


class CustomJSON(TypeDecorator):
    """
    JSON column type that stores ``None`` as database NULL instead of the string ``'null'``.
    """

    impl = JSON
    cache_ok = True

    @property
    def python_type(self):
        # The column holds any JSON value, so no single Python type applies.
        # SQLAlchemy 2.1 answers ``object`` here where 2.0 raises; raise on both
        # so consumers keep treating the type as undeclared.
        raise NotImplementedError("CustomJSON accepts arbitrary JSON values")

    def bind_processor(self, dialect) -> Optional[Callable[[Any], Any]]:
        process = self.impl.bind_processor(dialect)

        def process_value(value: Any) -> Any:
            if value is None:
                return None
            if process is None:
                return value
            return process(value)

        return process_value

    def result_processor(self, dialect, coltype) -> Optional[Callable[[Any], Any]]:
        process = self.impl.result_processor(dialect, coltype)

        def process_value(value: Any) -> Any:
            if process is None:
                return value
            return process(value)

        return process_value
