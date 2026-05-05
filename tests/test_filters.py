"""
How django-filterly works
=========================

The library turns raw HTTP query-string params into a filtered Django QuerySet
through a four-step pipeline:

  1. PARSE   (parser.py)
     ─────────────────────────────────────────────────────────────────────────
     parse_params(params)  →  list[FilterDescriptor]

     Accepts a plain dict or a Django QueryDict.
     Each key is split into (field_path, lookup):

       Key style            Example                   Result
       ────────────────────────────────────────────────────────────
       ORM __              "age__gte"              → field="age"  lookup="gte"
       ORM deep            "user__email__icontains" → field="user__email"
                                                      lookup="icontains"
       No lookup suffix    "name"                  → field="name" lookup="exact"
       Flat relation       "user_email_icontains"  → field="user__email"
                                                      lookup="icontains"
       Plain _ field       "is_active"             → field="is_active"
                                                      lookup="exact"
       NOT lookup          "status__not"           → field="status"
                                                      lookup="exact" exclude=True
       Multi-value list    {"status": ["a","b"]}   → field="status"
                                                      lookup="in" value=["a","b"]

  2. VALIDATE  (validators.py)
     ─────────────────────────────────────────────────────────────────────────
     validate_all(descriptors, model=..., allowed_fields=..., allowed_lookups=...)

     Checks performed in order, raises FilterValidationError on first failure:
       1. field in allowed_fields whitelist       → code "field_not_allowed"
       2. lookup in SUPPORTED_LOOKUPS             → code "lookup_not_supported"
       3. lookup in allowed_lookups whitelist     → code "lookup_not_allowed"
       4. field path exists on model              → code "field_does_not_exist"
                                                         "not_a_relation"
       5. lookup valid for field's data type      → code "lookup_incompatible"

  3. TRANSFORM  (transformers.py)
     ─────────────────────────────────────────────────────────────────────────
     transform_value(descriptor, field_type=..., custom_transformers=...)

     Priority order:
       1. custom_transformers[field] callable
       2. Lookup-forced rules  (isnull→bool, year/month/day/…→int, date→date)
       3. __in / __overlap     → list, element-coerced by field_type
       4. __range              → 2-element list, element-coerced by field_type
       5. field_type scalar    → number/date/datetime/time/boolean
       6. Fallback             → raw string (text, json, relation, unknown)

  4. APPLY  (filterset.py)
     ─────────────────────────────────────────────────────────────────────────
     FilterSet(...).qs   →  filtered QuerySet

     Each descriptor becomes one ORM keyword argument, chained as AND:
       exclude=False  →  qs.filter(field__lookup=value)
       exclude=True   →  qs.exclude(field__exact=value)

Test map
========
  TestParser          → step 1: all key-parsing branches
  TestQueryDictCompat → step 1: QueryDict simulation
  TestTransformers    → step 3: all individual converter functions
  TestTransformValue  → step 3: transform_value() routing logic
  TestValidators      → step 2: all validation checks + error codes
  TestFilterSet       → full pipeline with a mock QuerySet
  TestExceptions      → exception structure and attributes
  TestEdgeCases       → whitespace, empty values, boundary inputs

How to run the tests
====================

1. Install dependencies (once)
   ─────────────────────────────
   pip install django pytest

2. Run all tests
   ─────────────────────────────
   pytest tests/

3. Run with verbose output (see every test name)
   ─────────────────────────────
   pytest tests/ -v

4. Run a single test class
   ─────────────────────────────
   pytest tests/test_filters.py::TestParser -v
   pytest tests/test_filters.py::TestTransformers -v
   pytest tests/test_filters.py::TestValidators -v
   pytest tests/test_filters.py::TestFilterSet -v

5. Run a single test by name
   ─────────────────────────────
   pytest tests/test_filters.py::TestParser::test_orm_style_field_and_known_lookup -v
   pytest tests/test_filters.py::TestToBool::test_true_values -v

6. Run only tests that match a keyword
   ─────────────────────────────
   pytest tests/ -k "bool"          # all tests with "bool" in the name
   pytest tests/ -k "not django"    # skip tests that require Django

7. Stop on first failure
   ─────────────────────────────
   pytest tests/ -x

8. Show local variable values on failure
   ─────────────────────────────
   pytest tests/ -l

9. Run with coverage report
   ─────────────────────────────
   pip install pytest-cov
   pytest tests/ --cov=django_filterly --cov-report=term-missing

10. Run only tests that do NOT need Django (pure unit tests)
    ─────────────────────────────
    pytest tests/ -m "not skipif"
    # or filter by class:
    pytest tests/test_filters.py::TestParser
    pytest tests/test_filters.py::TestTransformers
    pytest tests/test_filters.py::TestExceptions
    pytest tests/test_filters.py::TestEdgeCases

Notes
─────
- Tests marked with @requires_django are skipped when Django is not installed.
- MockQuerySet is used instead of a real database — no migrations needed.
- All tests are self-contained and run without a Django settings module.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

import pytest  # type: ignore[import]

from django_filterly.constants import (
    BOOLEAN_FALSE_VALUES,
    BOOLEAN_TRUE_VALUES,
    DEFAULT_LOOKUP,
    SUPPORTED_LOOKUPS,
)
from django_filterly.exceptions import (
    FilterValidationError,
    FilterValueError,
)
from django_filterly.filterset import FilterSet
from django_filterly.parser import FilterDescriptor, parse_params
from django_filterly.transformers import (
    to_bool,
    to_date,
    to_datetime,
    to_decimal,
    to_float,
    to_int,
    to_list,
    to_number,
    to_range,
    to_str,
    to_time,
    to_uuid,
    transform_value,
)
from django_filterly.validators import validate_all, validate_filter


# ===========================================================================
# Fake model infrastructure
# (avoids requiring a real Django app / database for unit tests)
# ===========================================================================

try:
    from django.core.exceptions import FieldDoesNotExist  # type: ignore[import]
    _DJANGO_AVAILABLE = True
except ImportError:  # pragma: no cover
    class FieldDoesNotExist(Exception):  # type: ignore[no-redef]
        pass
    _DJANGO_AVAILABLE = False

requires_django = pytest.mark.skipif(
    not _DJANGO_AVAILABLE,
    reason="Django not installed",
)


def _field(class_name: str, related_model=None):
    """Create a fake Django field instance whose class name matches the map."""
    cls = type(class_name, (), {})
    obj = cls()
    if related_model is not None:
        obj.related_model = related_model  # type: ignore[attr-defined]
    return obj


class _FakeMeta:
    def __init__(self, fields: dict):
        self._fields = fields

    def get_field(self, name):
        if name in self._fields:
            return self._fields[name]
        raise FieldDoesNotExist(name)


class FakeUserModel:
    __name__ = "FakeUser"
    _meta = _FakeMeta({
        "email": _field("CharField"),
        "age":   _field("IntegerField"),
    })


class FakeProductModel:
    __name__ = "FakeProduct"
    _meta = _FakeMeta({
        "name":       _field("CharField"),
        "price":      _field("DecimalField"),
        "stock":      _field("IntegerField"),
        "is_active":  _field("BooleanField"),
        "created_at": _field("DateTimeField"),
        "updated_at": _field("DateTimeField"),
        "deleted_at": _field("DateTimeField"),
        "meta":       _field("JSONField"),
        "tags":       _field("ArrayField"),
        "owner":      _field("ForeignKey", related_model=FakeUserModel),
        "user_id":    _field("IntegerField"),
    })


class MockQuerySet:
    """Records filter/exclude calls without a database."""

    def __init__(self, model=None):
        self.model    = model or FakeProductModel
        self._filters  = []
        self._excludes = []

    def filter(self, **kwargs):
        clone = MockQuerySet(model=self.model)
        clone._filters  = self._filters + [kwargs]
        clone._excludes = list(self._excludes)
        return clone

    def exclude(self, **kwargs):
        clone = MockQuerySet(model=self.model)
        clone._filters  = list(self._filters)
        clone._excludes = self._excludes + [kwargs]
        return clone


def _desc(field, lookup=DEFAULT_LOOKUP, value="x", exclude=False):
    """Shorthand to build a FilterDescriptor."""
    return FilterDescriptor(field=field, lookup=lookup, value=value, exclude=exclude)


def _qs(model=None):
    return MockQuerySet(model=model)


# ===========================================================================
# TestParser
# ===========================================================================

class TestParser:

    def test_empty_params_returns_empty_list(self):
        assert parse_params({}) == []

    def test_simple_field_gets_default_lookup(self):
        [d] = parse_params({"name": "shirt"})
        assert d.field  == "name"
        assert d.lookup == DEFAULT_LOOKUP
        assert d.value  == "shirt"
        assert d.exclude is False

    def test_orm_style_field_and_known_lookup(self):
        [d] = parse_params({"age__gte": "25"})
        assert d.field  == "age"
        assert d.lookup == "gte"

    def test_orm_style_deep_relation(self):
        [d] = parse_params({"user__email__icontains": "gmail"})
        assert d.field  == "user__email"
        assert d.lookup == "icontains"

    def test_unknown_suffix_treated_as_field_name(self):
        [d] = parse_params({"custom__field": "val"})
        assert d.field  == "custom__field"
        assert d.lookup == DEFAULT_LOOKUP

    def test_flat_style_relation_with_lookup(self):
        [d] = parse_params({"user_email_icontains": "gmail"})
        assert d.field  == "user__email"
        assert d.lookup == "icontains"

    def test_flat_style_deep_relation_with_lookup(self):
        [d] = parse_params({"order_total_gte": "100"})
        assert d.field  == "order__total"
        assert d.lookup == "gte"

    def test_plain_underscore_field_is_not_flat_notation(self):
        """is_active, created_at, user_id must not be misread as flat notation."""
        for key in ("is_active", "created_at", "user_id"):
            [d] = parse_params({key: "val"})
            assert d.field  == key, f"Failed for key={key!r}"
            assert d.lookup == DEFAULT_LOOKUP

    def test_not_lookup_sets_exclude_flag(self):
        [d] = parse_params({"status__not": "draft"})
        assert d.exclude is True

    def test_not_lookup_normalised_to_exact(self):
        [d] = parse_params({"status__not": "draft"})
        assert d.lookup == "exact"

    def test_list_value_promoted_to_in(self):
        [d] = parse_params({"status": ["active", "inactive"]})
        assert d.lookup == "in"
        assert d.value  == ["active", "inactive"]

    def test_explicit_in_lookup_not_double_promoted(self):
        [d] = parse_params({"status__in": "active,inactive"})
        assert d.lookup == "in"
        assert d.value  == "active,inactive"   # string, not already a list

    def test_isnull_lookup_parsed(self):
        [d] = parse_params({"deleted_at__isnull": "true"})
        assert d.field  == "deleted_at"
        assert d.lookup == "isnull"

    def test_range_lookup_parsed(self):
        [d] = parse_params({"price__range": "10,500"})
        assert d.field  == "price"
        assert d.lookup == "range"

    def test_multiple_params_returns_multiple_descriptors(self):
        result = parse_params({"name__icontains": "x", "price__gte": "50"})
        assert len(result) == 2

    def test_all_fields_in_result_are_filter_descriptors(self):
        result = parse_params({"a": "1", "b__gte": "2"})
        assert all(isinstance(d, FilterDescriptor) for d in result)


# ===========================================================================
# TestQueryDictCompat
# ===========================================================================

class _FakeQueryDict:
    """Minimal QueryDict stub that satisfies _is_querydict() duck-type check."""
    def __init__(self, data: dict[str, list]):
        self._data = data

    def getlist(self, key):
        return self._data.get(key, [])

    def lists(self):
        return self._data.items()


class TestQueryDictCompat:

    def test_single_value_querydict(self):
        qd = _FakeQueryDict({"name__icontains": ["shirt"]})
        [d] = parse_params(qd)
        assert d.value == "shirt"

    def test_multi_value_querydict_promoted_to_in(self):
        qd = _FakeQueryDict({"status": ["active", "pending"]})
        [d] = parse_params(qd)
        assert d.lookup == "in"
        assert d.value  == ["active", "pending"]

    def test_multi_value_with_explicit_in_lookup(self):
        qd = _FakeQueryDict({"status__in": ["active", "pending"]})
        [d] = parse_params(qd)
        assert d.lookup == "in"

    def test_empty_querydict_returns_empty(self):
        assert parse_params(_FakeQueryDict({})) == []


# ===========================================================================
# TestTransformers — individual converter functions
# ===========================================================================

class TestToBool:

    @pytest.mark.parametrize("val", sorted(BOOLEAN_TRUE_VALUES))
    def test_true_values(self, val):
        assert to_bool(val, field="f", lookup="exact") is True

    @pytest.mark.parametrize("val", sorted(BOOLEAN_FALSE_VALUES))
    def test_false_values(self, val):
        assert to_bool(val, field="f", lookup="exact") is False

    def test_already_bool_true(self):
        assert to_bool(True, field="f", lookup="exact") is True

    def test_already_bool_false(self):
        assert to_bool(False, field="f", lookup="exact") is False

    def test_invalid_raises_with_code(self):
        with pytest.raises(FilterValueError) as exc_info:
            to_bool("maybe", field="is_active", lookup="exact")
        assert exc_info.value.code == "invalid_bool"
        assert exc_info.value.field == "is_active"

    def test_case_insensitive(self):
        assert to_bool("TRUE", field="f", lookup="exact") is True
        assert to_bool("False", field="f", lookup="exact") is False


class TestToInt:

    def test_integer_string(self):
        assert to_int("42", field="age", lookup="gte") == 42

    def test_negative_integer_string(self):
        assert to_int("-10", field="age", lookup="lt") == -10

    def test_already_int(self):
        assert to_int(42, field="age", lookup="exact") == 42

    def test_bool_input_treated_as_int(self):
        # bool is a subclass of int; we reject it to avoid silent coercion
        result = to_int(1, field="age", lookup="exact")
        assert result == 1

    def test_invalid_string_raises(self):
        with pytest.raises(FilterValueError) as exc_info:
            to_int("abc", field="age", lookup="gte")
        assert exc_info.value.code == "invalid_int"

    def test_float_string_raises(self):
        with pytest.raises(FilterValueError):
            to_int("3.14", field="age", lookup="exact")


class TestToFloat:

    def test_float_string(self):
        assert to_float("3.14", field="price", lookup="gte") == pytest.approx(3.14)

    def test_already_float(self):
        assert to_float(3.14, field="price", lookup="gte") == pytest.approx(3.14)

    def test_integer_string_becomes_float(self):
        assert to_float("10", field="price", lookup="exact") == 10.0

    def test_invalid_raises(self):
        with pytest.raises(FilterValueError) as exc_info:
            to_float("abc", field="price", lookup="gte")
        assert exc_info.value.code == "invalid_float"


class TestToDecimal:

    def test_decimal_string(self):
        from decimal import Decimal
        assert to_decimal("9.99", field="price", lookup="exact") == Decimal("9.99")

    def test_already_decimal(self):
        from decimal import Decimal
        d = Decimal("1.23")
        assert to_decimal(d, field="price", lookup="exact") == d

    def test_invalid_raises(self):
        with pytest.raises(FilterValueError) as exc_info:
            to_decimal("xyz", field="price", lookup="exact")
        assert exc_info.value.code == "invalid_decimal"


class TestToNumber:

    def test_int_string_returns_int(self):
        result = to_number("42", field="age", lookup="exact")
        assert result == 42
        assert isinstance(result, int)

    def test_float_string_returns_float(self):
        result = to_number("3.14", field="price", lookup="gte")
        assert isinstance(result, float)

    def test_negative_int(self):
        assert to_number("-5", field="stock", lookup="lt") == -5

    def test_invalid_raises(self):
        with pytest.raises(FilterValueError) as exc_info:
            to_number("nope", field="price", lookup="gte")
        assert exc_info.value.code == "invalid_number"


class TestToDate:

    def test_iso_date_string(self):
        assert to_date("2024-01-15", field="created_at", lookup="date") == date(2024, 1, 15)

    def test_already_date(self):
        d = date(2024, 1, 15)
        assert to_date(d, field="created_at", lookup="exact") == d

    def test_datetime_instance_coerced_to_date(self):
        # datetime is a subclass of date — extract the date part
        dt = datetime(2024, 1, 15)
        assert to_date(dt, field="f", lookup="exact") == date(2024, 1, 15)

    def test_invalid_raises(self):
        with pytest.raises(FilterValueError) as exc_info:
            to_date("not-a-date", field="created_at", lookup="date")
        assert exc_info.value.code == "invalid_date"


class TestToDatetime:

    def test_naive_datetime(self):
        result = to_datetime("2024-01-15T10:30:00", field="created_at", lookup="gte")
        assert result == datetime(2024, 1, 15, 10, 30, 0)

    def test_z_suffix_parsed(self):
        result = to_datetime("2024-01-15T10:30:00Z", field="created_at", lookup="gte")
        assert result.tzinfo is not None

    def test_offset_parsed(self):
        result = to_datetime("2024-01-15T10:30:00+05:00", field="created_at", lookup="gte")
        assert result.tzinfo is not None

    def test_space_separator(self):
        result = to_datetime("2024-01-15 10:30:00", field="created_at", lookup="exact")
        assert result == datetime(2024, 1, 15, 10, 30, 0)

    def test_already_datetime(self):
        dt = datetime(2024, 6, 1)
        assert to_datetime(dt, field="f", lookup="exact") == dt

    def test_invalid_raises(self):
        with pytest.raises(FilterValueError) as exc_info:
            to_datetime("not-a-datetime", field="created_at", lookup="gte")
        assert exc_info.value.code == "invalid_datetime"


class TestToTime:

    def test_hh_mm(self):
        assert to_time("10:30", field="updated_at", lookup="exact") == time(10, 30)

    def test_hh_mm_ss(self):
        assert to_time("10:30:45", field="updated_at", lookup="exact") == time(10, 30, 45)

    def test_already_time(self):
        t = time(9, 0)
        assert to_time(t, field="f", lookup="exact") == t

    def test_invalid_raises(self):
        with pytest.raises(FilterValueError) as exc_info:
            to_time("not-time", field="updated_at", lookup="exact")
        assert exc_info.value.code == "invalid_time"


class TestToUuid:

    def test_valid_uuid_string(self):
        raw = "12345678-1234-5678-1234-567812345678"
        result = to_uuid(raw, field="uid", lookup="exact")
        assert result == uuid.UUID(raw)

    def test_already_uuid(self):
        u = uuid.uuid4()
        assert to_uuid(u, field="uid", lookup="exact") == u

    def test_invalid_raises(self):
        with pytest.raises(FilterValueError) as exc_info:
            to_uuid("not-a-uuid", field="uid", lookup="exact")
        assert exc_info.value.code == "invalid_uuid"


class TestToStr:

    def test_string_value(self):
        assert to_str("hello", field="name", lookup="exact") == "hello"

    def test_non_string_coerced(self):
        assert to_str(42, field="name", lookup="exact") == "42"

    def test_none_raises(self):
        with pytest.raises(FilterValueError) as exc_info:
            to_str(None, field="name", lookup="exact")
        assert exc_info.value.code == "null_value"


class TestToList:

    def test_comma_separated_string(self):
        assert to_list("a,b,c", field="status", lookup="in") == ["a", "b", "c"]

    def test_already_a_list(self):
        assert to_list(["a", "b"], field="status", lookup="in") == ["a", "b"]

    def test_strips_whitespace(self):
        assert to_list(" a , b ", field="status", lookup="in") == ["a", "b"]

    def test_empty_string_raises(self):
        with pytest.raises(FilterValueError) as exc_info:
            to_list("", field="status", lookup="in")
        assert exc_info.value.code == "empty_list"

    def test_element_fn_applied(self):
        result = to_list("1,2,3", field="age", lookup="in", element_fn=to_int)
        assert result == [1, 2, 3]

    def test_wrong_type_raises(self):
        with pytest.raises(FilterValueError) as exc_info:
            to_list(42, field="status", lookup="in")
        assert exc_info.value.code == "invalid_list_format"


class TestToRange:

    def test_two_values(self):
        assert to_range("10,500", field="price", lookup="range") == ["10", "500"]

    def test_one_value_raises(self):
        with pytest.raises(FilterValueError) as exc_info:
            to_range("10", field="price", lookup="range")
        assert exc_info.value.code == "invalid_range"

    def test_three_values_raises(self):
        with pytest.raises(FilterValueError) as exc_info:
            to_range("1,2,3", field="price", lookup="range")
        assert exc_info.value.code == "invalid_range"

    def test_element_fn_applied(self):
        result = to_range("10,500", field="price", lookup="range", element_fn=to_int)
        assert result == [10, 500]

    def test_already_a_two_element_list(self):
        assert to_range(["10", "500"], field="price", lookup="range") == ["10", "500"]


# ===========================================================================
# TestTransformValue — routing logic of transform_value()
# ===========================================================================

class TestTransformValue:

    def _d(self, field, lookup, value):
        return FilterDescriptor(field=field, lookup=lookup, value=value)

    # --- lookup-forced rules ---

    def test_isnull_converted_to_bool(self):
        d = self._d("deleted_at", "isnull", "true")
        assert transform_value(d) is True

    @pytest.mark.parametrize("lookup", ["year", "month", "day", "week", "week_day"])
    def test_date_parts_converted_to_int(self, lookup):
        d = self._d("created_at", lookup, "5")
        assert transform_value(d) == 5

    @pytest.mark.parametrize("lookup", ["hour", "minute", "second"])
    def test_time_parts_converted_to_int(self, lookup):
        d = self._d("updated_at", lookup, "10")
        assert transform_value(d) == 10

    def test_len_converted_to_int(self):
        d = self._d("tags", "len", "3")
        assert transform_value(d) == 3

    def test_date_lookup_converted_to_date_object(self):
        d = self._d("created_at", "date", "2024-06-01")
        assert transform_value(d) == date(2024, 6, 1)

    # --- __in / __overlap ---

    def test_in_without_field_type_returns_string_list(self):
        d = self._d("status", "in", "active,inactive")
        result = transform_value(d)
        assert result == ["active", "inactive"]

    def test_in_with_number_field_type_coerces_elements(self):
        d = self._d("age", "in", "1,2,3")
        result = transform_value(d, field_type="number")
        assert result == [1, 2, 3]

    def test_overlap_treated_like_in(self):
        d = self._d("tags", "overlap", "a,b")
        result = transform_value(d)
        assert result == ["a", "b"]

    # --- __range ---

    def test_range_without_field_type_returns_string_list(self):
        d = self._d("price", "range", "10,500")
        result = transform_value(d)
        assert result == ["10", "500"]

    def test_range_with_number_field_type_coerces_elements(self):
        d = self._d("price", "range", "10,500")
        result = transform_value(d, field_type="number")
        assert result == [10, 500]

    # --- field-type scalar coercion ---

    def test_number_field_type_coerces_scalar(self):
        d = self._d("age", "exact", "25")
        assert transform_value(d, field_type="number") == 25

    def test_boolean_field_type_coerces_scalar(self):
        d = self._d("is_active", "exact", "true")
        assert transform_value(d, field_type="boolean") is True

    def test_date_field_type_coerces_scalar(self):
        d = self._d("created_at", "exact", "2024-01-01")
        assert transform_value(d, field_type="date") == date(2024, 1, 1)

    def test_datetime_field_type_coerces_scalar(self):
        d = self._d("created_at", "gte", "2024-01-01T00:00:00")
        result = transform_value(d, field_type="datetime")
        assert isinstance(result, datetime)

    # --- custom transformer priority ---

    def test_custom_transformer_overrides_everything(self):
        called_with = {}

        def my_transformer(value, *, field, lookup):
            called_with.update(field=field, lookup=lookup, value=value)
            return "CUSTOM"

        d = self._d("price", "exact", "99")
        result = transform_value(
            d,
            field_type="number",
            custom_transformers={"price": my_transformer},
        )
        assert result == "CUSTOM"
        assert called_with["field"] == "price"

    # --- fallback ---

    def test_fallback_returns_raw_string(self):
        d = self._d("meta", "has_key", "color")
        assert transform_value(d, field_type="json") == "color"

    def test_unknown_field_type_falls_back_to_raw(self):
        d = self._d("some_field", "exact", "hello")
        assert transform_value(d, field_type="unknown_type") == "hello"


# ===========================================================================
# TestValidators
# ===========================================================================

class TestValidators:

    # --- field whitelist ---

    def test_field_not_in_whitelist_raises(self):
        d = _desc("secret_field", "exact")
        with pytest.raises(FilterValidationError) as exc_info:
            validate_filter(d, allowed_fields={"name", "price"})
        assert exc_info.value.code  == "field_not_allowed"
        assert exc_info.value.field == "secret_field"

    def test_field_in_whitelist_passes(self):
        d = _desc("name", "icontains", "shirt")
        validate_filter(d, allowed_fields={"name", "price"})  # no exception

    def test_no_whitelist_accepts_any_field(self):
        d = _desc("any_field", "exact")
        validate_filter(d)  # no exception

    # --- lookup supported ---

    def test_unsupported_lookup_raises(self):
        d = _desc("name", "fake_lookup")
        with pytest.raises(FilterValidationError) as exc_info:
            validate_filter(d)
        assert exc_info.value.code   == "lookup_not_supported"
        assert exc_info.value.lookup == "fake_lookup"

    def test_all_supported_lookups_pass(self):
        for lookup in SUPPORTED_LOOKUPS:
            d = _desc("name", lookup)
            validate_filter(d)  # no exception

    # --- lookup whitelist ---

    def test_lookup_not_in_whitelist_raises(self):
        d = _desc("name", "regex")
        with pytest.raises(FilterValidationError) as exc_info:
            validate_filter(d, allowed_lookups={"exact", "icontains"})
        assert exc_info.value.code   == "lookup_not_allowed"
        assert exc_info.value.lookup == "regex"

    def test_lookup_in_whitelist_passes(self):
        d = _desc("name", "icontains", "shirt")
        validate_filter(d, allowed_lookups={"exact", "icontains"})  # no exception

    # --- model-level: field existence ---

    @requires_django
    def test_field_does_not_exist_on_model_raises(self):
        d = _desc("ghost_field", "exact")
        with pytest.raises(FilterValidationError) as exc_info:
            validate_filter(d, model=FakeProductModel)
        assert exc_info.value.code == "field_does_not_exist"

    @requires_django
    def test_valid_field_on_model_passes(self):
        d = _desc("name", "icontains", "shirt")
        validate_filter(d, model=FakeProductModel)  # no exception

    @requires_django
    def test_traversal_of_non_relation_field_raises(self):
        # "name" is a CharField — cannot traverse further
        d = _desc("name__subfield", "exact")
        with pytest.raises(FilterValidationError) as exc_info:
            validate_filter(d, model=FakeProductModel)
        assert exc_info.value.code == "not_a_relation"

    @requires_django
    def test_fk_traversal_valid(self):
        d = _desc("owner__email", "icontains", "gmail")
        validate_filter(d, model=FakeProductModel)  # no exception

    @requires_django
    def test_fk_traversal_field_not_found_raises(self):
        d = _desc("owner__ghost", "exact")
        with pytest.raises(FilterValidationError) as exc_info:
            validate_filter(d, model=FakeProductModel)
        assert exc_info.value.code == "field_does_not_exist"

    # --- model-level: type compatibility ---

    @requires_django
    def test_lookup_incompatible_with_field_type_raises(self):
        # "year" is only valid for date/datetime, not for CharField
        d = _desc("name", "year")
        with pytest.raises(FilterValidationError) as exc_info:
            validate_filter(d, model=FakeProductModel)
        assert exc_info.value.code == "lookup_incompatible"

    @requires_django
    def test_compatible_lookup_passes(self):
        d = _desc("price", "gte", "50")
        validate_filter(d, model=FakeProductModel)  # DecimalField + gte → OK

    # --- validate_all ---

    def test_validate_all_empty_list_passes(self):
        validate_all([])  # no exception

    def test_validate_all_raises_on_first_invalid(self):
        descriptors = [
            _desc("name", "icontains", "shirt"),   # valid
            _desc("name", "bad_lookup"),            # invalid
            _desc("price", "gte", "10"),            # never reached
        ]
        with pytest.raises(FilterValidationError) as exc_info:
            validate_all(descriptors)
        assert exc_info.value.lookup == "bad_lookup"

    def test_validate_all_valid_list_passes(self):
        descriptors = [
            _desc("name",  "icontains", "shirt"),
            _desc("price", "gte",       "50"),
            _desc("is_active", "exact", "true"),
        ]
        validate_all(descriptors)  # no exception


# ===========================================================================
# TestFilterSet
# ===========================================================================

class TestFilterSet:

    def test_empty_params_returns_original_queryset_unchanged(self):
        qs = _qs()
        result = FilterSet(queryset=qs, params={}).qs
        assert result._filters  == []
        assert result._excludes == []

    @requires_django
    def test_single_filter_applied(self):
        qs = _qs()
        result = FilterSet(queryset=qs, params={"stock__gte": "5"}).qs
        assert result._filters == [{"stock__gte": 5}]

    @requires_django
    def test_multiple_filters_are_all_chained(self):
        qs = _qs()
        result = FilterSet(
            queryset=qs,
            params={"name__icontains": "shirt", "is_active": "true"},
        ).qs
        assert len(result._filters) == 2

    @requires_django
    def test_not_lookup_becomes_exclude(self):
        qs = _qs()
        result = FilterSet(queryset=qs, params={"name__not": "draft"}).qs
        assert result._excludes == [{"name__exact": "draft"}]
        assert result._filters  == []

    def test_model_inferred_from_queryset(self):
        qs = _qs(model=FakeProductModel)
        fs = FilterSet(queryset=qs, params={})
        assert fs.model is FakeProductModel

    def test_allowed_fields_blocks_disallowed_field(self):
        qs = _qs()
        with pytest.raises(FilterValidationError) as exc_info:
            FilterSet(
                queryset=qs,
                params={"price__gte": "50"},
                allowed_fields={"name"},
            ).qs
        assert exc_info.value.code == "field_not_allowed"

    def test_allowed_lookups_blocks_disallowed_lookup(self):
        qs = _qs()
        with pytest.raises(FilterValidationError) as exc_info:
            FilterSet(
                queryset=qs,
                params={"name__regex": r"^T"},
                allowed_lookups={"exact", "icontains"},
            ).qs
        assert exc_info.value.code == "lookup_not_allowed"

    @requires_django
    def test_custom_transformer_applied(self):
        def my_transformer(value, *, field, lookup):  # noqa: ARG001
            _ = field, lookup
            return int(value) * 100

        qs = _qs()
        result = FilterSet(
            queryset=qs,
            params={"stock__gte": "2"},
            custom_transformers={"stock": my_transformer},
        ).qs
        assert result._filters == [{"stock__gte": 200}]

    @requires_django
    def test_orm_key_format_is_field_double_underscore_lookup(self):
        qs = _qs()
        result = FilterSet(queryset=qs, params={"name__icontains": "shirt"}).qs
        assert "name__icontains" in result._filters[0]

    @requires_django
    def test_boolean_value_coerced_to_bool(self):
        qs = _qs()
        result = FilterSet(queryset=qs, params={"is_active": "true"}).qs
        assert result._filters[0] == {"is_active__exact": True}

    @requires_django
    def test_isnull_coerced_to_bool(self):
        qs = _qs()
        result = FilterSet(queryset=qs, params={"deleted_at__isnull": "true"}).qs
        assert result._filters[0] == {"deleted_at__isnull": True}

    @requires_django
    def test_in_query_with_comma_string(self):
        qs = _qs()
        result = FilterSet(
            queryset=qs,
            params={"stock__in": "1,2,3"},
        ).qs
        assert result._filters[0] == {"stock__in": [1, 2, 3]}

    @requires_django
    def test_range_query_coerced_to_list(self):
        qs = _qs()
        result = FilterSet(
            queryset=qs,
            params={"stock__range": "1,100"},
        ).qs
        assert result._filters[0] == {"stock__range": [1, 100]}


# ===========================================================================
# TestExceptions
# ===========================================================================

class TestExceptions:

    def test_filter_validation_error_is_exception(self):
        e = FilterValidationError("msg", field="name", lookup="gte", code="bad")
        assert isinstance(e, Exception)
        assert str(e) == "msg"

    def test_filter_validation_error_attributes(self):
        e = FilterValidationError(
            "msg", field="name", lookup="gte", value="x", code="lookup_not_supported"
        )
        assert e.field  == "name"
        assert e.lookup == "gte"
        assert e.value  == "x"
        assert e.code   == "lookup_not_supported"

    def test_filter_validation_error_repr(self):
        e = FilterValidationError("msg", field="f", lookup="l", code="c")
        r = repr(e)
        assert "field='f'"  in r
        assert "lookup='l'" in r
        assert "code='c'"   in r

    def test_filter_value_error_attributes(self):
        e = FilterValueError(
            "msg", field="age", lookup="gte",
            value="abc", expected_type="int", code="invalid_int",
        )
        assert e.field         == "age"
        assert e.value         == "abc"
        assert e.expected_type == "int"
        assert e.code          == "invalid_int"

    def test_filter_value_error_repr(self):
        e = FilterValueError("msg", field="f", value="v", expected_type="int", code="c")
        r = repr(e)
        assert "value='v'"         in r
        assert "expected_type='int'" in r

    def test_none_optional_fields_default_to_none(self):
        e = FilterValidationError("bare")
        assert e.field  is None
        assert e.lookup is None
        assert e.code   is None


# ===========================================================================
# TestEdgeCases
# ===========================================================================

class TestEdgeCases:

    def test_value_with_leading_trailing_spaces_stripped(self):
        # to_int strips whitespace before parsing
        assert to_int("  42  ", field="age", lookup="exact") == 42

    def test_comma_list_with_spaces_stripped(self):
        result = to_list(" a , b , c ", field="status", lookup="in")
        assert result == ["a", "b", "c"]

    def test_range_with_spaces_stripped(self):
        result = to_range(" 10 , 500 ", field="price", lookup="range")
        assert result == ["10", "500"]

    def test_bool_with_uppercase_true(self):
        assert to_bool("TRUE", field="f", lookup="exact") is True

    def test_bool_with_mixed_case_yes(self):
        assert to_bool("Yes", field="f", lookup="exact") is True

    def test_parse_params_with_none_like_key_is_unchanged(self):
        [d] = parse_params({"id": "1"})
        assert d.field == "id"

    def test_flat_notation_minimum_three_segments(self):
        # "a_b" has only 2 segments — must NOT be treated as flat notation
        [d] = parse_params({"a_b": "val"})
        assert d.field  == "a_b"
        assert d.lookup == DEFAULT_LOOKUP

    def test_flat_notation_exact_three_segments(self):
        # "rel_field_icontains" → 3 segments, last is known lookup
        [d] = parse_params({"rel_field_icontains": "val"})
        assert d.field  == "rel__field"
        assert d.lookup == "icontains"

    def test_supported_lookups_is_nonempty_set(self):
        assert len(SUPPORTED_LOOKUPS) > 0

    def test_default_lookup_is_exact(self):
        assert DEFAULT_LOOKUP == "exact"

    def test_filter_descriptor_defaults(self):
        d = FilterDescriptor(field="name", lookup="exact", value="x")
        assert d.exclude is False
