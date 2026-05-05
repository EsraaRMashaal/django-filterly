from __future__ import annotations

from typing import Any


class FilterlyError(Exception):
    """Base class for all django-filterly exceptions."""


class FilterValidationError(FilterlyError):
    """Raised when a filter param is structurally invalid.

    Covers:
      - field not in the allowed whitelist
      - lookup not supported at all
      - lookup not in the allowed whitelist
      - lookup incompatible with the field's data type
      - field path does not exist on the model
      - intermediate relation in a traversal path does not exist
    """

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        lookup: str | None = None,
        value: Any = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.field = field
        self.lookup = lookup
        self.value = value
        self.code = code

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"field={self.field!r}, "
            f"lookup={self.lookup!r}, "
            f"code={self.code!r}, "
            f"message={str(self)!r})"
        )


class FilterValueError(FilterlyError):
    """Raised when a raw string value cannot be coerced to the expected type.

    Covers:
      - non-numeric string for an integer/float field
      - invalid ISO date string
      - non-boolean string for a boolean field
      - range/in with wrong number of elements
    """

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        lookup: str | None = None,
        value: Any = None,
        expected_type: str | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.field = field
        self.lookup = lookup
        self.value = value
        self.expected_type = expected_type
        self.code = code

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}("
            f"field={self.field!r}, "
            f"lookup={self.lookup!r}, "
            f"value={self.value!r}, "
            f"expected_type={self.expected_type!r}, "
            f"code={self.code!r})"
        )


class FilterConfigError(FilterlyError):
    """Raised when FilterSet itself is misconfigured by the developer.

    Covers:
      - invalid option types passed to FilterSet
      - allowed_fields / allowed_lookups contain unrecognised values
      - conflicting options
    """
