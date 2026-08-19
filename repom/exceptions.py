from sqlalchemy.exc import DontWrapMixin


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
