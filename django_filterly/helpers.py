from __future__ import annotations

from typing import Any

from .constants import LOOKUP_SEPARATOR
from .exceptions import FilterConfigError, FilterValidationError

try:
    from django.core.exceptions import FieldDoesNotExist  # type: ignore[import]
except ImportError as exc:  # pragma: no cover
    raise FilterConfigError(
        "django-filterly requires Django to be installed. "
        "Run: pip install django"
    ) from exc


# ---------------------------------------------------------------------------
# Django field class → filterly type string
# ---------------------------------------------------------------------------

_DJANGO_FIELD_TYPE_MAP: dict[str, str] = {
    # Text
    "CharField": "text",
    "TextField": "text",
    "EmailField": "text",
    "URLField": "text",
    "SlugField": "text",
    "UUIDField": "text",
    "FileField": "text",
    "FilePathField": "text",
    "IPAddressField": "text",
    "GenericIPAddressField": "text",
    # Numbers
    "IntegerField": "number",
    "BigIntegerField": "number",
    "SmallIntegerField": "number",
    "PositiveIntegerField": "number",
    "PositiveBigIntegerField": "number",
    "PositiveSmallIntegerField": "number",
    "AutoField": "number",
    "BigAutoField": "number",
    "SmallAutoField": "number",
    "FloatField": "number",
    "DecimalField": "number",
    # Dates & times
    "DateField": "date",
    "DateTimeField": "datetime",
    "TimeField": "time",
    "DurationField": "number",
    # Boolean
    "BooleanField": "boolean",
    "NullBooleanField": "boolean",
    # Relations
    "ForeignKey": "relation",
    "OneToOneField": "relation",
    "ManyToManyField": "relation",
    "ManyToOneRel": "relation",
    "ManyToManyRel": "relation",
    "OneToOneRel": "relation",
    # Structured
    "JSONField": "json",
    "ArrayField": "array",  # PostgreSQL only
}


def get_field_type(field_obj: Any) -> str:
    """Return the filterly type string for a Django field instance.

    Falls back to "text" for unknown / custom field types so the library
    never hard-crashes on an unrecognised field class.
    """
    return _DJANGO_FIELD_TYPE_MAP.get(type(field_obj).__name__, "text")


def resolve_field_on_model(field_path: str, model: Any) -> Any:
    """Walk a '__'-separated field path on a Django model and return the
    terminal field object.

    Raises FilterValidationError with a precise message when:
      - a segment does not exist on its model  (code: 'field_does_not_exist')
      - a non-terminal segment is not a relation (code: 'not_a_relation')
    """
    parts = field_path.split(LOOKUP_SEPARATOR)
    current_model = model

    for index, part in enumerate(parts):
        try:
            field_obj = current_model._meta.get_field(part)
        except FieldDoesNotExist:
            raise FilterValidationError(
                f"Field '{part}' does not exist on model '{current_model.__name__}'. "
                f"Full path: '{field_path}'.",
                field=field_path,
                code="field_does_not_exist",
            )

        is_last = index == len(parts) - 1
        if not is_last:
            related = getattr(field_obj, "related_model", None)
            if related is None:
                raise FilterValidationError(
                    f"'{part}' on '{current_model.__name__}' is not a relation field "
                    f"and cannot be traversed. Full path: '{field_path}'.",
                    field=field_path,
                    code="not_a_relation",
                )
            current_model = related

    return field_obj
