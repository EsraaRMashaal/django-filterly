# constants.py — Shared constants and default configuration for django-filterly

# ---------------------------------------------------------------------------
# Separators & defaults
# ---------------------------------------------------------------------------

LOOKUP_SEPARATOR = "__"
# Separator between field name and lookup in query params (e.g. "price__gte")

DEFAULT_LOOKUP = "exact"
# Fallback lookup when the param key has no explicit lookup suffix

# ---------------------------------------------------------------------------
# Boolean value coercion
# ---------------------------------------------------------------------------

BOOLEAN_TRUE_VALUES = {"true", "1", "yes", "on"}
BOOLEAN_FALSE_VALUES = {"false", "0", "no", "off"}

# ---------------------------------------------------------------------------
# Lookups grouped by semantic category
# ---------------------------------------------------------------------------

# Equality
EXACT_LOOKUPS = {
    "exact",
    "iexact",
}

# Containment / pattern matching
TEXT_LOOKUPS = {
    "contains",
    "icontains",
    "startswith",
    "istartswith",
    "endswith",
    "iendswith",
}

# Regular expressions
REGEX_LOOKUPS = {
    "regex",
    "iregex",
}

# Numeric / date / time comparison
COMPARISON_LOOKUPS = {
    "gt",
    "gte",
    "lt",
    "lte",
}

# Date part extraction (DateField / DateTimeField)
DATE_PART_LOOKUPS = {
    "date",
    "year",
    "month",
    "day",
    "week",
    "week_day",
}

# Time part extraction (DateTimeField / TimeField)
TIME_PART_LOOKUPS = {
    "hour",
    "minute",
    "second",
}

# Set / range membership
SET_LOOKUPS = {
    "in",      # field__in=[v1, v2, ...]
    "range",   # field__range=[min, max]
}

# Negation — triggers queryset.exclude() instead of filter()
EXCLUDE_LOOKUPS = {
    "not",
}

# Null check
NULL_LOOKUPS = {
    "isnull",
}

# JSON field lookups (requires JSONField)
JSON_LOOKUPS = {
    "contains",
    "has_key",
    "has_any_keys",
    "has_keys",
}

# Array field lookups (PostgreSQL ArrayField only)
ARRAY_LOOKUPS = {
    "contains",
    "overlap",
    "len",
}

# ---------------------------------------------------------------------------
# Lookup sets grouped by field data type
# Used by validators to check if a lookup is valid for a given field type
# ---------------------------------------------------------------------------

FIELD_TYPE_LOOKUPS = {
    "text":     EXACT_LOOKUPS | TEXT_LOOKUPS | REGEX_LOOKUPS | SET_LOOKUPS | NULL_LOOKUPS | EXCLUDE_LOOKUPS,
    "number":   EXACT_LOOKUPS | COMPARISON_LOOKUPS | SET_LOOKUPS | NULL_LOOKUPS | EXCLUDE_LOOKUPS,
    "date":     EXACT_LOOKUPS | COMPARISON_LOOKUPS | DATE_PART_LOOKUPS | SET_LOOKUPS | NULL_LOOKUPS | EXCLUDE_LOOKUPS,
    "datetime": EXACT_LOOKUPS | COMPARISON_LOOKUPS | DATE_PART_LOOKUPS | TIME_PART_LOOKUPS | SET_LOOKUPS | NULL_LOOKUPS | EXCLUDE_LOOKUPS,
    "time":     EXACT_LOOKUPS | COMPARISON_LOOKUPS | TIME_PART_LOOKUPS | NULL_LOOKUPS | EXCLUDE_LOOKUPS,
    "boolean":  EXACT_LOOKUPS | NULL_LOOKUPS | EXCLUDE_LOOKUPS,
    "relation": EXACT_LOOKUPS | SET_LOOKUPS | NULL_LOOKUPS | EXCLUDE_LOOKUPS,
    "json":     JSON_LOOKUPS | NULL_LOOKUPS,
    "array":    ARRAY_LOOKUPS | NULL_LOOKUPS,
}

# ---------------------------------------------------------------------------
# Master set of every supported lookup keyword across all field types
# ---------------------------------------------------------------------------

SUPPORTED_LOOKUPS = (
    EXACT_LOOKUPS
    | TEXT_LOOKUPS
    | REGEX_LOOKUPS
    | COMPARISON_LOOKUPS
    | DATE_PART_LOOKUPS
    | TIME_PART_LOOKUPS
    | SET_LOOKUPS
    | EXCLUDE_LOOKUPS
    | NULL_LOOKUPS
    | JSON_LOOKUPS
    | ARRAY_LOOKUPS
)
