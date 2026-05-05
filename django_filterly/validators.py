from __future__ import annotations

from typing import Any

from .constants import FIELD_TYPE_LOOKUPS, SUPPORTED_LOOKUPS
from .exceptions import FilterValidationError
from .helpers import get_field_type, resolve_field_on_model
from .parser import FilterDescriptor


# ---------------------------------------------------------------------------
# Individual validation checks
# ---------------------------------------------------------------------------

def _check_field_whitelist(
    field: str,
    allowed_fields: set[str] | None,
) -> None:
    """Raise if the field is not in the caller's allowed_fields whitelist."""
    if allowed_fields is not None and field not in allowed_fields:
        raise FilterValidationError(
            f"Field '{field}' is not in the allowed fields list.",
            field=field,
            code="field_not_allowed",
        )


def _check_lookup_supported(field: str, lookup: str) -> None:
    """Raise if the lookup keyword is not supported at all by this library."""
    if lookup not in SUPPORTED_LOOKUPS:
        raise FilterValidationError(
            f"Lookup '{lookup}' is not supported. "
            f"Supported lookups: {sorted(SUPPORTED_LOOKUPS)}.",
            field=field,
            lookup=lookup,
            code="lookup_not_supported",
        )


def _check_lookup_whitelist(
    field: str,
    lookup: str,
    allowed_lookups: set[str] | None,
) -> None:
    """Raise if the lookup is not in the caller's allowed_lookups whitelist."""
    if allowed_lookups is not None and lookup not in allowed_lookups:
        raise FilterValidationError(
            f"Lookup '{lookup}' is not in the allowed lookups list.",
            field=field,
            lookup=lookup,
            code="lookup_not_allowed",
        )


def _check_lookup_type_compatibility(
    field_path: str,
    lookup: str,
    model: Any,
) -> None:
    """Resolve the field on the model, detect its type, and confirm the
    lookup is valid for that type.

    Raises FilterValidationError with code 'lookup_incompatible' when the
    lookup does not apply to this field's data type.
    """
    field_obj  = resolve_field_on_model(field_path, model)
    field_type = get_field_type(field_obj)
    valid_lookups = FIELD_TYPE_LOOKUPS.get(field_type, SUPPORTED_LOOKUPS)

    if lookup not in valid_lookups:
        raise FilterValidationError(
            f"Lookup '{lookup}' is not valid for field '{field_path}' "
            f"(type: {field_type}). "
            f"Valid lookups for this type: {sorted(valid_lookups)}.",
            field=field_path,
            lookup=lookup,
            code="lookup_incompatible",
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_filter(
    descriptor: FilterDescriptor,
    *,
    model: Any = None,
    allowed_fields: set[str] | list[str] | None = None,
    allowed_lookups: set[str] | list[str] | None = None,
) -> None:
    """Validate a single FilterDescriptor and raise FilterValidationError on
    the first problem found.

    Checks performed (in order):
      1. field in allowed_fields whitelist        → code: 'field_not_allowed'
      2. lookup in SUPPORTED_LOOKUPS              → code: 'lookup_not_supported'
      3. lookup in allowed_lookups whitelist      → code: 'lookup_not_allowed'
      4. field exists on model (if model given)   → code: 'field_does_not_exist'
                                                         'not_a_relation'
      5. lookup compatible with field type        → code: 'lookup_incompatible'
    """
    _allowed_fields  = set(allowed_fields)  if allowed_fields  is not None else None
    _allowed_lookups = set(allowed_lookups) if allowed_lookups is not None else None

    _check_field_whitelist(descriptor.field, _allowed_fields)
    _check_lookup_supported(descriptor.field, descriptor.lookup)
    _check_lookup_whitelist(descriptor.field, descriptor.lookup, _allowed_lookups)

    if model is not None:
        _check_lookup_type_compatibility(descriptor.field, descriptor.lookup, model)


def validate_all(
    descriptors: list[FilterDescriptor],
    *,
    model: Any = None,
    allowed_fields: set[str] | list[str] | None = None,
    allowed_lookups: set[str] | list[str] | None = None,
) -> None:
    """Validate every descriptor in the list.

    Raises FilterValidationError on the first invalid descriptor found.
    """
    for descriptor in descriptors:
        validate_filter(
            descriptor,
            model=model,
            allowed_fields=allowed_fields,
            allowed_lookups=allowed_lookups,
        )
