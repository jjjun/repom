from sqlalchemy.exc import DontWrapMixin, IntegrityError


class NulByteError(ValueError, DontWrapMixin):
    """Raised when a value contains a NUL byte that cannot be stored."""

    def __init__(self, column_name: str, offset: int, key_path: str | None = None):
        self.column_name = column_name
        self.offset = offset
        self.key_path = key_path
        safe_key_path = key_path.replace('\0', '\\u0000') if key_path is not None else None
        location = f" at key path '{safe_key_path}'" if safe_key_path is not None else ''
        super().__init__(
            f"NUL (0x00) byte at offset {offset} in column '{column_name}'{location} is not storable"
        )


def is_unique_violation(exc: IntegrityError) -> bool:
    """Return whether an integrity error represents a unique constraint violation."""
    original = exc.orig
    sqlstate = getattr(original, 'sqlstate', None)
    pgcode = getattr(original, 'pgcode', None)
    if sqlstate is not None or pgcode is not None:
        return sqlstate == '23505' or pgcode == '23505'

    sqlite_errorname = getattr(original, 'sqlite_errorname', None)
    if sqlite_errorname is not None:
        return sqlite_errorname in {
            'SQLITE_CONSTRAINT_UNIQUE',
            'SQLITE_CONSTRAINT_PRIMARYKEY',
        }

    return 'unique' in str(original or exc).lower()


def unique_violation_constraint_name(exc: IntegrityError) -> str | None:
    """Return the violated unique constraint name when the driver exposes it."""
    diagnostic = getattr(exc.orig, 'diag', None)
    return getattr(diagnostic, 'constraint_name', None)
