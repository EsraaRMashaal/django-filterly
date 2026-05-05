from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from .constants import BOOLEAN_FALSE_VALUES, BOOLEAN_TRUE_VALUES
from .exceptions import FilterValueError
from .parser import FilterDescriptor


# ---------------------------------------------------------------------------
# Scalar transformers
# Each function receives the raw value plus (field, lookup) for error context.
# ---------------------------------------------------------------------------

def to_bool(value: Any, *, field: str, lookup: str) -> bool:
    """Convert a string to bool using the allowed truth/false sets.

    Accepts: "true", "1", "yes", "on"  → True
             "false", "0", "no", "off" → False
    """
    if isinstance(value, bool):
        return value
    normalised = str(value).strip().lower()
    if normalised in BOOLEAN_TRUE_VALUES:
        return True
    if normalised in BOOLEAN_FALSE_VALUES:
        return False
    raise FilterValueError(
        f"Cannot convert '{value}' to bool for field '{field}'. "
        f"Accepted values: {sorted(BOOLEAN_TRUE_VALUES | BOOLEAN_FALSE_VALUES)}.",
        field=field, lookup=lookup, value=value,
        expected_type="bool", code="invalid_bool",
    )


def to_int(value: Any, *, field: str, lookup: str) -> int:
    """Convert a string to int."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        raise FilterValueError(
            f"Cannot convert '{value}' to int for field '{field}'.",
            field=field, lookup=lookup, value=value,
            expected_type="int", code="invalid_int",
        )


def to_float(value: Any, *, field: str, lookup: str) -> float:
    """Convert a string to float."""
    if isinstance(value, float):
        return value
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        raise FilterValueError(
            f"Cannot convert '{value}' to float for field '{field}'.",
            field=field, lookup=lookup, value=value,
            expected_type="float", code="invalid_float",
        )


def to_decimal(value: Any, *, field: str, lookup: str) -> Decimal:
    """Convert a string to Decimal (for DecimalField precision)."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).strip())
    except InvalidOperation:
        raise FilterValueError(
            f"Cannot convert '{value}' to Decimal for field '{field}'.",
            field=field, lookup=lookup, value=value,
            expected_type="Decimal", code="invalid_decimal",
        )


def to_number(value: Any, *, field: str, lookup: str) -> int | float:
    """Convert a string to int if it is a whole number, otherwise float.

    Used for generic "number" field type when the exact subtype is unknown.
    DecimalField precision is handled by Django itself after this coercion.
    """
    raw = str(value).strip()
    try:
        as_int = int(raw)
        # Only return int when there is no fractional part
        if "." not in raw:
            return as_int
    except (ValueError, TypeError):
        pass
    try:
        return float(raw)
    except (ValueError, TypeError):
        raise FilterValueError(
            f"Cannot convert '{value}' to a number for field '{field}'.",
            field=field, lookup=lookup, value=value,
            expected_type="number", code="invalid_number",
        )


def to_date(value: Any, *, field: str, lookup: str) -> date:
    """Convert an ISO 8601 date string (YYYY-MM-DD) to a date object."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        raise FilterValueError(
            f"Cannot convert '{value}' to date for field '{field}'. "
            "Expected ISO 8601 format: YYYY-MM-DD.",
            field=field, lookup=lookup, value=value,
            expected_type="date", code="invalid_date",
        )


def to_datetime(value: Any, *, field: str, lookup: str) -> datetime:
    """Convert an ISO 8601 datetime string to a datetime object.

    Handles:
      "2024-01-15T10:30:00"           → naive datetime
      "2024-01-15T10:30:00Z"          → UTC datetime
      "2024-01-15T10:30:00+05:30"     → offset-aware datetime
      "2024-01-15 10:30:00"           → naive datetime (space separator)
    """
    if isinstance(value, datetime):
        return value
    raw = str(value).strip()
    # Python < 3.11 fromisoformat does not handle the "Z" UTC suffix
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        raise FilterValueError(
            f"Cannot convert '{value}' to datetime for field '{field}'. "
            "Expected ISO 8601 format: YYYY-MM-DDTHH:MM:SS[±HH:MM].",
            field=field, lookup=lookup, value=value,
            expected_type="datetime", code="invalid_datetime",
        )


def to_time(value: Any, *, field: str, lookup: str) -> time:
    """Convert a time string (HH:MM or HH:MM:SS) to a time object."""
    if isinstance(value, time):
        return value
    try:
        return time.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        raise FilterValueError(
            f"Cannot convert '{value}' to time for field '{field}'. "
            "Expected format: HH:MM or HH:MM:SS.",
            field=field, lookup=lookup, value=value,
            expected_type="time", code="invalid_time",
        )


def to_uuid(value: Any, *, field: str, lookup: str) -> uuid.UUID:
    """Convert a UUID string to a uuid.UUID object."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value).strip())
    except (ValueError, AttributeError):
        raise FilterValueError(
            f"Cannot convert '{value}' to UUID for field '{field}'. "
            "Expected format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.",
            field=field, lookup=lookup, value=value,
            expected_type="uuid", code="invalid_uuid",
        )


def to_str(value: Any, *, field: str, lookup: str) -> str:
    """Return value as a plain string (no-op for text fields)."""
    if value is None:
        raise FilterValueError(
            f"Field '{field}' with lookup '{lookup}' received a null value.",
            field=field, lookup=lookup, value=value,
            expected_type="str", code="null_value",
        )
    return str(value)


# ---------------------------------------------------------------------------
# Collection transformers  (__in, __range, __overlap)
# ---------------------------------------------------------------------------

def _split_raw(value: Any, *, field: str, lookup: str) -> list[str]:
    """Split a comma-separated string or return an existing list as-is.

    Strips whitespace from each element and removes empty entries.
    """
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip() != ""]
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
        return [p for p in parts if p != ""]
    raise FilterValueError(
        f"Expected a list or comma-separated string for field '{field}' "
        f"with lookup '{lookup}', got {type(value).__name__}.",
        field=field, lookup=lookup, value=value,
        expected_type="list", code="invalid_list_format",
    )


def to_list(
    value: Any,
    *,
    field: str,
    lookup: str,
    element_fn: Callable | None = None,
) -> list:
    """Convert comma-separated string or list into a Python list.

    If element_fn is provided it is applied to every element
    (e.g. to_int for age__in=1,2,3).
    """
    parts = _split_raw(value, field=field, lookup=lookup)
    if not parts:
        raise FilterValueError(
            f"Empty value for '{field}__{lookup}'. Provide at least one item.",
            field=field, lookup=lookup, value=value,
            expected_type="list", code="empty_list",
        )
    if element_fn is None:
        return parts
    return [element_fn(p, field=field, lookup=lookup) for p in parts]


def to_range(
    value: Any,
    *,
    field: str,
    lookup: str,
    element_fn: Callable | None = None,
) -> list:
    """Convert a value into a two-element list for Django's __range lookup.

    Input:  "100,500"        → [100, 500]   (with element_fn=to_int)
            ["100", "500"]   → [100, 500]
    """
    parts = _split_raw(value, field=field, lookup=lookup)
    if len(parts) != 2:
        raise FilterValueError(
            f"'__range' for field '{field}' requires exactly 2 values "
            f"(min,max), got {len(parts)}.",
            field=field, lookup=lookup, value=value,
            expected_type="range", code="invalid_range",
        )
    if element_fn is None:
        return parts
    return [element_fn(p, field=field, lookup=lookup) for p in parts]


# ---------------------------------------------------------------------------
# Lookup-forced transformer map
# These lookups ALWAYS require a specific Python type regardless of field type.
# ---------------------------------------------------------------------------

#: lookup → (transformer_fn, needs_element_fn)
#: needs_element_fn=True means the transformer accepts an element_fn argument
#: for per-element coercion inside lists (used for __in and __range).
_LOOKUP_TRANSFORMER: dict[str, Callable] = {
    # Null check → bool
    "isnull": to_bool,
    # Date parts → int
    "year":     to_int,
    "month":    to_int,
    "day":      to_int,
    "week":     to_int,
    "week_day": to_int,
    # Time parts → int
    "hour":     to_int,
    "minute":   to_int,
    "second":   to_int,
    # Array length → int
    "len":      to_int,
    # Date lookup on DateTimeField → date object
    "date":     to_date,
}

#: field_type → scalar transformer  (for __in / __range element coercion
#:                                   and direct scalar field conversion)
_TYPE_TRANSFORMER: dict[str, Callable] = {
    "number":   to_number,
    "date":     to_date,
    "datetime": to_datetime,
    "time":     to_time,
    "boolean":  to_bool,
    "text":     to_str,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transform_value(
    descriptor: FilterDescriptor,
    *,
    field_type: str | None = None,
    custom_transformers: dict[str, Callable] | None = None,
) -> Any:
    """Transform the raw string value in a FilterDescriptor to the correct
    Python type.

    Priority order:
      1. custom_transformers[field_path]  — caller-defined override per field
      2. Lookup-forced rules              — __isnull → bool, date parts → int …
      3. __in  / __overlap               — list, with element coercion by type
      4. __range                         — 2-element list, with element coercion
      5. Field-type scalar coercion      — number/date/datetime/time/boolean
      6. Raw string fallback             — text, json, relation, unknown types

    Parameters
    ----------
    descriptor:
        Parsed filter from parser.parse_params().
    field_type:
        Filterly type string ("number", "date", "datetime", "time",
        "boolean", "text", "json", "array", "relation").
        When None, only lookup-forced rules and collection rules apply.
    custom_transformers:
        Dict of {field_path: callable} for field-level overrides.
        The callable receives (value, field=..., lookup=...) and must
        return the transformed value.
    """
    field   = descriptor.field
    lookup  = descriptor.lookup
    value   = descriptor.value

    # 1. Custom per-field override
    if custom_transformers and field in custom_transformers:
        return custom_transformers[field](value, field=field, lookup=lookup)

    # 2. Lookup-forced scalar rules (isnull, date/time parts, __date, __len)
    if lookup in _LOOKUP_TRANSFORMER:
        return _LOOKUP_TRANSFORMER[lookup](value, field=field, lookup=lookup)

    # Resolve element-level coercion function for collections
    element_fn: Callable | None = _TYPE_TRANSFORMER.get(field_type) if field_type else None

    # 3. List lookups (__in, __overlap)
    if lookup in {"in", "overlap"}:
        return to_list(value, field=field, lookup=lookup, element_fn=element_fn)

    # 4. Range lookup (__range)
    if lookup == "range":
        return to_range(value, field=field, lookup=lookup, element_fn=element_fn)

    # 5. Scalar coercion driven by field type
    if field_type and field_type in _TYPE_TRANSFORMER:
        return _TYPE_TRANSFORMER[field_type](value, field=field, lookup=lookup)

    # 6. Fallback — return as-is (text, json, relation, unknown)
    return value


def transform_all(
    descriptors: list[FilterDescriptor],
    *,
    field_types: dict[str, str] | None = None,
    custom_transformers: dict[str, Callable] | None = None,
) -> list[tuple[FilterDescriptor, Any]]:
    """Transform every descriptor and return (descriptor, transformed_value) pairs.

    Parameters
    ----------
    field_types:
        Dict of {field_path: filterly_type_string} so each descriptor can
        get the correct element coercion.  Built by FilterSet from the model.
    custom_transformers:
        Per-field callable overrides forwarded to transform_value().

    Raises FilterValueError on the first value that cannot be converted.
    """
    field_types = field_types or {}
    result: list[tuple[FilterDescriptor, Any]] = []

    for descriptor in descriptors:
        field_type = field_types.get(descriptor.field)
        transformed = transform_value(
            descriptor,
            field_type=field_type,
            custom_transformers=custom_transformers,
        )
        result.append((descriptor, transformed))

    return result
