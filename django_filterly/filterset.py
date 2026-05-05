from __future__ import annotations

from typing import Any, Callable

from .exceptions import FilterValidationError
from .helpers import get_field_type, resolve_field_on_model
from .parser import FilterDescriptor, parse_params
from .transformers import transform_all
from .validators import validate_all


class FilterSet:
    """Main entry point for django-filterly.

    Wires together parsing → validation → transformation → queryset filtering.
    Access the result via the `.qs` property.

    Parameters
    ----------
    queryset:
        Any Django QuerySet. The model is inferred from queryset.model.
    params:
        Raw filter params — a plain dict or a Django QueryDict (request.GET).
    allowed_fields:
        Whitelist of field paths the caller permits filtering on.
        When None, all fields are accepted.
    allowed_lookups:
        Whitelist of lookup keywords the caller permits.
        When None, every supported lookup is accepted.
    custom_transformers:
        Dict of { field_path: callable } for per-field value conversion
        overrides. The callable signature is (value, *, field, lookup) → Any.

    Usage
    -----
    Basic::

        qs = FilterSet(
            queryset=Product.objects.all(),
            params=request.GET,
        ).qs

    With restrictions::

        qs = FilterSet(
            queryset=Order.objects.select_related("user"),
            params=request.GET,
            allowed_fields={"status", "user__email", "created_at"},
            allowed_lookups={"exact", "icontains", "gte", "lte"},
        ).qs
    """

    def __init__(
        self,
        queryset: Any,
        params: Any,
        *,
        allowed_fields: set[str] | list[str] | None = None,
        allowed_lookups: set[str] | list[str] | None = None,
        custom_transformers: dict[str, Callable] | None = None,
    ) -> None:
        self.queryset            = queryset
        self.model               = queryset.model
        self.params              = params
        self.allowed_fields      = allowed_fields
        self.allowed_lookups     = allowed_lookups
        self.custom_transformers = custom_transformers or {}
        self._qs_cache: Any      = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def qs(self) -> Any:
        """Run the full pipeline and return the filtered QuerySet.

        The result is cached — accessing .qs multiple times on the same
        FilterSet instance does not re-run the pipeline.

        Pipeline:
          1. parse      — query params → FilterDescriptors
          2. validate   — check fields, lookups, and type compatibility
          3. transform  — coerce raw strings to proper Python types
          4. apply      — chain .filter() / .exclude() on the QuerySet
        """
        if self._qs_cache is None:
            descriptors     = self._parse()
            self._validate(descriptors)
            field_types     = self._collect_field_types(descriptors)
            pairs           = self._transform(descriptors, field_types)
            self._qs_cache  = self._apply(pairs)
        return self._qs_cache

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _parse(self) -> list[FilterDescriptor]:
        """Step 1 — delegate to parser."""
        return parse_params(self.params)

    def _validate(self, descriptors: list[FilterDescriptor]) -> None:
        """Step 2 — validate every descriptor, raise on the first invalid one."""
        validate_all(
            descriptors,
            model=self.model,
            allowed_fields=self.allowed_fields,
            allowed_lookups=self.allowed_lookups,
        )

    def _collect_field_types(
        self, descriptors: list[FilterDescriptor]
    ) -> dict[str, str]:
        """Step 2.5 — build a {field_path: filterly_type} map for the transformer."""
        field_types: dict[str, str] = {}
        for descriptor in descriptors:
            try:
                field_obj = resolve_field_on_model(descriptor.field, self.model)
                field_types[descriptor.field] = get_field_type(field_obj)
            except FilterValidationError:
                pass
        return field_types

    def _transform(
        self,
        descriptors: list[FilterDescriptor],
        field_types: dict[str, str],
    ) -> list[tuple[FilterDescriptor, Any]]:
        """Step 3 — coerce raw string values to typed Python objects."""
        return transform_all(
            descriptors,
            field_types=field_types,
            custom_transformers=self.custom_transformers,
        )

    def _apply(self, pairs: list[tuple[FilterDescriptor, Any]]) -> Any:
        """Step 4 — chain .filter() / .exclude() calls onto the QuerySet."""
        qs = self.queryset

        for descriptor, value in pairs:
            orm_key = f"{descriptor.field}__{descriptor.lookup}"
            if descriptor.exclude:
                qs = qs.exclude(**{orm_key: value})
            else:
                qs = qs.filter(**{orm_key: value})

        return qs
