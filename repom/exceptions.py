from sqlalchemy.exc import DontWrapMixin


class NulByteError(ValueError, DontWrapMixin):
    """Raised when a value contains a NUL byte that cannot be stored."""

    def __init__(self, column_name: str, offset: int):
        self.column_name = column_name
        self.offset = offset
        super().__init__(
            f"NUL (0x00) byte at offset {offset} in column '{column_name}' is not storable"
        )
