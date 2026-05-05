from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .constants import (
    DEFAULT_LOOKUP,
    EXCLUDE_LOOKUPS,
    LOOKUP_SEPARATOR,
    SUPPORTED_LOOKUPS,
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FilterDescriptor:
    """One parsed filter ready for the FilterSet to apply.

    field   — ORM field path, e.g. "user__email", "created_at"
    lookup  — ORM lookup keyword, e.g. "icontains", "gte", "in"
    value   — raw value(s) from the query string (str, list, or None)
    exclude — True when the original lookup was "not" → triggers .exclude()
    """
    field: str
    lookup: str
    value: Any
    exclude: bool = False


# ---------------------------------------------------------------------------
# QueryDict compatibility
# ---------------------------------------------------------------------------

def _is_querydict(params: Any) -> bool:
    """Duck-type check for Django QueryDict (avoids importing Django here)."""
    return hasattr(params, "getlist") and hasattr(params, "lists")


def _iter_params(params: Any) -> list[tuple[str, Any]]:
    """Yield (key, value) pairs from a plain dict or a Django QueryDict.

    For QueryDict keys that appear more than once (e.g. ?tag=a&tag=b)
    the value is returned as a list so the FilterSet can apply __in.
    """
    if _is_querydict(params):
        return [
            (key, values if len(values) > 1 else values[0])
            for key, values in params.lists()
        ]
    return list(params.items())


# ---------------------------------------------------------------------------
# Key parsing strategies
# ---------------------------------------------------------------------------

def _parse_orm_style(key: str) -> tuple[str, str]:
    """Parse a double-underscore key into (field_path, lookup).

    Rules:
      - Split on "__"
      - If the last segment is a known lookup → strip it, rest is the field path
      - Otherwise → treat the whole key as the field name, use DEFAULT_LOOKUP

    Examples:
      "name__icontains"          → ("name", "icontains")
      "user__email__icontains"   → ("user__email", "icontains")
      "created_at__year"         → ("created_at", "year")
      "age__gte"                 → ("age", "gte")
      "status__in"               → ("status", "in")
      "status__not"              → ("status", "not")
      "deleted_at__isnull"       → ("deleted_at", "isnull")
      "price__range"             → ("price", "range")
      "jsonfield__has_key"       → ("jsonfield", "has_key")
      "tags__overlap"            → ("tags", "overlap")
      "name__regex"              → ("name", "regex")
      "is_active"                → ("is_active", "exact")   ← no lookup suffix
    """
    parts = key.split(LOOKUP_SEPARATOR)
    if len(parts) > 1 and parts[-1] in SUPPORTED_LOOKUPS:
        field_path = LOOKUP_SEPARATOR.join(parts[:-1])
        return field_path, parts[-1]
    return key, DEFAULT_LOOKUP


def _parse_flat_style(key: str) -> tuple[str, str]:
    """Parse a flat single-underscore relation key into (field_path, lookup).

    This notation is used for FK / related-field traversal without "__":
      relation_field_lookup  →  relation__field  +  lookup

    Detection rule: the last "_"-separated segment must be a known lookup
    AND there must be at least 2 segments before it (relation + field).
    Without that, the whole key is treated as a plain field name.

    Examples (flat notation):
      "user_email_icontains"          → ("user__email",      "icontains")
      "profile_city_icontains"        → ("profile__city",    "icontains")
      "profile_companyname_icontains" → ("profile__companyname", "icontains")
      "order_total_gte"               → ("order__total",     "gte")
      "order_useremail_icontains"     → ("order__useremail", "icontains")

    Examples (plain field names — no flat conversion):
      "is_active"   → ("is_active",  "exact")   ← "active" not a lookup
      "user_id"     → ("user_id",    "exact")   ← "id" not a lookup
      "created_at"  → ("created_at", "exact")   ← "at" not a lookup
    """
    parts = key.split("_")
    if len(parts) >= 3 and parts[-1] in SUPPORTED_LOOKUPS:
        lookup = parts[-1]
        remaining = parts[:-1]
        # First segment = relation name, rest = field name (may contain underscores)
        field_path = remaining[0] + LOOKUP_SEPARATOR + "_".join(remaining[1:])
        return field_path, lookup
    return key, DEFAULT_LOOKUP


def _parse_key(key: str) -> tuple[str, str]:
    """Route a param key to the correct parsing strategy.

    Keys that contain "__" use ORM style.
    Keys that use only "_" (flat relation notation) use flat style.
    """
    if LOOKUP_SEPARATOR in key:
        return _parse_orm_style(key)
    return _parse_flat_style(key)


# ---------------------------------------------------------------------------
# Multi-value auto-promotion
# ---------------------------------------------------------------------------

def _resolve_list_value(value: Any, lookup: str) -> tuple[Any, str]:
    """If the value is a list and the lookup is still the default (exact),
    promote the lookup to "in" so the FilterSet applies field__in=[...].

    This handles QueryDict multi-values: ?status=a&status=b → status__in=[a,b]
    """
    if isinstance(value, list) and lookup == DEFAULT_LOOKUP:
        return value, "in"
    return value, lookup


# ---------------------------------------------------------------------------
# Exclude (NOT) normalisation
# ---------------------------------------------------------------------------

def _resolve_exclude(lookup: str) -> tuple[str, bool]:
    """Convert the custom "not" lookup into (DEFAULT_LOOKUP, exclude=True).

    The FilterSet uses exclude=True to call .exclude() instead of .filter().
    The ORM itself does not have a "not" lookup keyword.
    """
    if lookup in EXCLUDE_LOOKUPS:
        return DEFAULT_LOOKUP, True
    return lookup, False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_params(params: Any) -> list[FilterDescriptor]:
    """Parse raw query params into a list of FilterDescriptors.

    Accepts:
      - A plain Python dict:       {"age__gte": "25", "name__icontains": "ali"}
      - A Django QueryDict:        request.GET

    Returns a list of FilterDescriptor objects — one per query param key —
    ready for validators and the FilterSet to consume.

    Notation styles both supported:
      ORM style  → "user__email__icontains"   (double-underscore)
      Flat style → "user_email_icontains"      (single-underscore relation shorthand)
    """
    descriptors: list[FilterDescriptor] = []

    for key, value in _iter_params(params):
        field_path, lookup = _parse_key(key)
        value, lookup      = _resolve_list_value(value, lookup)
        lookup, exclude    = _resolve_exclude(lookup)

        descriptors.append(FilterDescriptor(
            field=field_path,
            lookup=lookup,
            value=value,
            exclude=exclude,
        ))

    return descriptors
