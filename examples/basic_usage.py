"""
django-filterly — comprehensive usage examples
===============================================

Each section is independent and runnable inside a Django project.
Replace the model stubs below with your own imports:

    from myapp.models import Product, Order, User
"""

# ---------------------------------------------------------------------------
# Model stubs — replace with your real imports in an actual project
# ---------------------------------------------------------------------------
# In a real Django project these would be:
#   from myapp.models import Product, Order, User
#
# The stubs below only exist so this file is self-contained and readable.

class _QuerySet:
    """Minimal queryset stub used by the model stubs below."""
    def all(self):            return self
    def filter(self):         return self
    def exclude(self):        return self
    def select_related(self): return self

class _Manager:
    def all(self):            return _QuerySet()
    def filter(self):         return _QuerySet()
    def select_related(self): return _QuerySet()

class _ModelBase:
    objects = _Manager()

class User(_ModelBase):
    """email, age, is_active, created_at"""

class Profile(_ModelBase):
    """user (O2O→User), country, city"""

class Product(_ModelBase):
    """name, price, stock, is_active, created_at, updated_at,
       deleted_at, tags (ArrayField), meta (JSONField), owner (FK→User)"""

class Order(_ModelBase):
    """user (FK→User), total, status, created_at"""


# ---------------------------------------------------------------------------
# Library imports
# ---------------------------------------------------------------------------

from django_filterly.exceptions import FilterValidationError, FilterValueError  # noqa: E402
from django_filterly.filterset import FilterSet                                  # noqa: E402
from django_filterly.parser import FilterDescriptor, parse_params               # noqa: E402
from django_filterly.transformers import to_bool, to_date, to_int               # noqa: E402
from django_filterly.validators import validate_filter                           # noqa: E402


# ===========================================================================
# 1. BASIC USAGE — one-liner inside a Django view
# ===========================================================================

def product_list_view(request):
    """Simplest usage: pass the queryset and request.GET, access .qs."""
    return FilterSet(
        queryset=Product.objects.all(),
        params=request.GET,
    ).qs
    # ?name__icontains=shirt  → WHERE name ILIKE '%shirt%'
    # ?price__gte=100         → WHERE price >= 100
    # ?is_active=true         → WHERE is_active = TRUE


# ===========================================================================
# 2. PLAIN DICT PARAMS — useful in tests or non-view code
# ===========================================================================

def filter_with_dict():
    """Pass a plain Python dict instead of request.GET."""
    return FilterSet(
        queryset=Product.objects.all(),
        params={"price__gte": "50", "is_active": "true"},
    ).qs


# ===========================================================================
# 3. TEXT LOOKUPS
# ===========================================================================

def text_filter_examples():
    base = Product.objects.all()
    cases = {
        "name__exact":       "T-Shirt",    # exact (case-sensitive)
        "name__iexact":      "t-shirt",    # exact (case-insensitive)
        "name__contains":    "shirt",      # substring (case-sensitive)
        "name__icontains":   "shirt",      # substring (case-insensitive)
        "name__startswith":  "T",          # prefix (case-sensitive)
        "name__istartswith": "t",          # prefix (case-insensitive)
        "name__endswith":    "Shirt",      # suffix (case-sensitive)
        "name__iendswith":   "shirt",      # suffix (case-insensitive)
        "name__regex":       r"^T.*t$",    # regex (case-sensitive)
        "name__iregex":      r"^t.*t$",    # regex (case-insensitive)
    }
    return [FilterSet(queryset=base, params={k: v}).qs for k, v in cases.items()]


# ===========================================================================
# 4. NUMERIC LOOKUPS  (int / float / decimal)
# ===========================================================================

def numeric_filter_examples():
    base = Product.objects.all()
    cases = [
        {"price__exact": "99.99"},     # exact value
        {"price__gt":    "50"},        # greater than
        {"price__gte":   "50"},        # greater than or equal
        {"price__lt":    "200"},       # less than
        {"price__lte":   "200"},       # less than or equal
        {"price__range": "50,200"},    # BETWEEN 50 AND 200
        {"stock__in":    "0,5,10"},    # IN (0, 5, 10)
    ]
    return [FilterSet(queryset=base, params=p).qs for p in cases]


# ===========================================================================
# 5. DATE & DATETIME LOOKUPS
# ===========================================================================

def date_filter_examples():
    base = Product.objects.all()
    cases = [
        {"created_at__exact":    "2024-01-15"},
        {"created_at__date":     "2024-01-15"},        # date part only
        {"created_at__year":     "2024"},
        {"created_at__month":    "1"},
        {"created_at__day":      "15"},
        {"created_at__week":     "3"},                 # ISO week number
        {"created_at__week_day": "2"},                 # 1=Sun … 7=Sat
        {"created_at__gte":      "2024-01-01T00:00"},
        {"created_at__lte":      "2024-12-31T23:59"},
        {"created_at__range":    "2024-01-01,2024-12-31"},
    ]
    return [FilterSet(queryset=base, params=p).qs for p in cases]


# ===========================================================================
# 6. TIME PART LOOKUPS
# ===========================================================================

def time_filter_examples():
    base = Product.objects.all()
    cases = [
        {"updated_at__hour":   "14"},
        {"updated_at__minute": "30"},
        {"updated_at__second": "0"},
        {"updated_at__gte":    "2024-06-01T00:00:00"},
        {"updated_at__lte":    "2024-06-30T23:59:59"},
    ]
    return [FilterSet(queryset=base, params=p).qs for p in cases]


# ===========================================================================
# 7. BOOLEAN LOOKUPS
# ===========================================================================

def boolean_filter_examples():
    base = Product.objects.all()

    # Accepted truth values
    for truth in ["true", "1", "yes", "on"]:
        FilterSet(queryset=base, params={"is_active": truth}).qs

    # Accepted false values
    for falsy in ["false", "0", "no", "off"]:
        FilterSet(queryset=base, params={"is_active": falsy}).qs

    # Explicit exact lookup
    return FilterSet(queryset=base, params={"is_active__exact": "true"}).qs


# ===========================================================================
# 8. NULL CHECKS
# ===========================================================================

def null_filter_examples():
    base = Product.objects.all()

    not_deleted = FilterSet(queryset=base, params={"deleted_at__isnull": "true"}).qs
    deleted     = FilterSet(queryset=base, params={"deleted_at__isnull": "false"}).qs

    return not_deleted, deleted


# ===========================================================================
# 9. NOT / EXCLUDE  (custom "not" lookup → .exclude())
# ===========================================================================

def exclude_filter_examples():
    # .exclude(status__exact="draft")
    return FilterSet(
        queryset=Product.objects.all(),
        params={"status__not": "draft"},
    ).qs


# ===========================================================================
# 10. IN QUERIES
# ===========================================================================

def in_filter_examples():
    base = Product.objects.all()

    # Comma-separated string in one param
    qs1 = FilterSet(queryset=base, params={"status__in": "active,pending,review"}).qs

    # Multi-value list — simulates ?status=active&status=pending from QueryDict
    # The parser auto-promotes a list value with no lookup to __in
    qs2 = FilterSet(queryset=base, params={"status": ["active", "pending"]}).qs

    return qs1, qs2


# ===========================================================================
# 11. RANGE QUERIES
# ===========================================================================

def range_filter_examples():
    base = Product.objects.all()

    numeric = FilterSet(queryset=base, params={"price__range": "10,500"}).qs
    dated   = FilterSet(queryset=base, params={"created_at__range": "2024-01-01,2024-06-30"}).qs

    return numeric, dated


# ===========================================================================
# 12. FOREIGN KEY TRAVERSAL — ORM double-underscore style
# ===========================================================================

def fk_filter_examples():
    qs1 = FilterSet(
        queryset=Product.objects.select_related("owner"),
        params={"owner__email__icontains": "gmail.com"},
    ).qs

    qs2 = FilterSet(
        queryset=Order.objects.select_related("user"),
        params={"user__age__gte": "18"},
    ).qs

    return qs1, qs2


# ===========================================================================
# 13. FLAT SINGLE-UNDERSCORE RELATION SHORTHAND
# ===========================================================================

def flat_notation_examples():
    """owner_email_icontains  →  owner__email  +  icontains lookup"""

    qs1 = FilterSet(
        queryset=Product.objects.select_related("owner"),
        params={"owner_email_icontains": "gmail.com"},
    ).qs

    qs2 = FilterSet(
        queryset=Order.objects.select_related("user"),
        params={"user_age_gte": "18"},
    ).qs

    return qs1, qs2


# ===========================================================================
# 14. DEEP / MULTI-HOP RELATIONS
# ===========================================================================

def deep_relation_examples():
    return FilterSet(
        queryset=Product.objects.select_related("owner__profile"),
        params={"owner__profile__city__icontains": "Cairo"},
    ).qs


# ===========================================================================
# 15. JSON FIELD LOOKUPS
# ===========================================================================

def json_filter_examples():
    base = Product.objects.all()
    cases = [
        {"meta__contains":     '{"color": "red"}'},  # JSON subset match
        {"meta__has_key":      "color"},              # key exists
        {"meta__has_any_keys": "color,size"},         # any key present
        {"meta__has_keys":     "color,size"},         # all keys present
    ]
    return [FilterSet(queryset=base, params=p).qs for p in cases]


# ===========================================================================
# 16. POSTGRESQL ARRAY FIELD LOOKUPS
# ===========================================================================

def array_filter_examples():
    base = Product.objects.all()
    cases = [
        {"tags__contains": "sale,new"},    # array contains all values
        {"tags__overlap":  "sale,promo"},  # array shares at least one value
        {"tags__len":      "3"},           # array length equals 3
    ]
    return [FilterSet(queryset=base, params=p).qs for p in cases]


# ===========================================================================
# 17. WHITELIST — restrict allowed fields and lookups
# ===========================================================================

def whitelist_examples():
    # "name__icontains" will raise FilterValidationError — field not allowed
    return FilterSet(
        queryset=Product.objects.all(),
        params={"price__gte": "100", "name__icontains": "shirt"},
        allowed_fields={"price", "status"},
        allowed_lookups={"exact", "gte", "lte", "in"},
    ).qs


# ===========================================================================
# 18. CUSTOM TRANSFORMERS — override value coercion per field
# ===========================================================================

def custom_transformer_examples():
    """Per-field callable: (value, *, field, lookup) → typed value."""

    def parse_price_with_currency(value, *, field, lookup):
        """Strip a currency prefix before converting to float.

        Raises FilterValueError so the error carries field/lookup context.
        """
        cleaned = str(value).lstrip("$€£¥").strip()
        try:
            return float(cleaned)
        except ValueError:
            raise FilterValueError(
                f"Cannot parse '{value}' as a price for field '{field}'.",
                field=field, lookup=lookup, value=value,
                expected_type="float", code="invalid_price",
            )

    return FilterSet(
        queryset=Product.objects.all(),
        params={"price__gte": "$100.00"},
        custom_transformers={"price": parse_price_with_currency},
    ).qs


# ===========================================================================
# 19. COMBINED FILTERS — multiple params, all ANDed
# ===========================================================================

def combined_filter_example(request):
    """All query params are applied as AND conditions."""
    return FilterSet(
        queryset=Product.objects.select_related("owner").all(),
        params=request.GET,
        allowed_fields={"name", "price", "is_active", "created_at", "owner__email"},
        allowed_lookups={"icontains", "gte", "lte", "exact", "year"},
    ).qs


# ===========================================================================
# 20. DRF — inside a ListAPIView
# ===========================================================================

# class ProductListView(ListAPIView):
#     serializer_class = ProductSerializer
#
#     def get_queryset(self):
#         return FilterSet(
#             queryset=Product.objects.all(),
#             params=self.request.GET,
#             allowed_fields={"name", "price", "is_active", "created_at"},
#             allowed_lookups={"exact", "icontains", "gte", "lte", "range"},
#         ).qs


# ===========================================================================
# 21. SUBCLASSING FilterSet — reusable defaults per model
# ===========================================================================

class ProductFilterSet(FilterSet):
    """FilterSet subclass with Product-specific defaults baked in."""

    _FIELDS = {
        "name", "price", "stock", "is_active",
        "created_at", "updated_at", "deleted_at",
        "owner__email", "owner__age",
        "tags", "meta",
    }
    _LOOKUPS = {
        "exact", "iexact", "icontains",
        "gt", "gte", "lt", "lte", "range", "in",
        "isnull", "not", "year", "month", "date",
    }

    def __init__(self, params, *, queryset=None, **kwargs):
        super().__init__(
            queryset=queryset or Product.objects.all(),
            params=params,
            allowed_fields=kwargs.pop("allowed_fields", self._FIELDS),
            allowed_lookups=kwargs.pop("allowed_lookups", self._LOOKUPS),
            **kwargs,
        )


def subclass_usage(request):
    return ProductFilterSet(request.GET).qs


# ===========================================================================
# 22. LOW-LEVEL — using individual modules directly
# ===========================================================================

def low_level_parser_example():
    """Use parse_params() when you only need the parsing step."""
    descriptors = parse_params({"price__gte": "100", "name__icontains": "shirt"})
    for d in descriptors:
        print(f"field={d.field!r}  lookup={d.lookup!r}  value={d.value!r}  exclude={d.exclude}")
    # field='price'  lookup='gte'       value='100'    exclude=False
    # field='name'   lookup='icontains'  value='shirt'  exclude=False
    return descriptors


def low_level_validator_example():
    """Use validate_filter() for single-descriptor validation."""
    descriptor = FilterDescriptor(field="price", lookup="gte", value="100")

    try:
        validate_filter(
            descriptor,
            model=Product,
            allowed_fields={"price", "name"},
            allowed_lookups={"gte", "lte", "icontains"},
        )
        print("Valid!")
    except FilterValidationError as e:
        print(f"Invalid — field={e.field}  code={e.code}  message={e}")


def low_level_transformer_example():
    """Use individual transformer functions directly."""
    print(to_int("42",          field="age",        lookup="gte"))    # → 42
    print(to_bool("yes",        field="is_active",  lookup="exact"))  # → True
    print(to_date("2024-01-15", field="created_at", lookup="date"))   # → date(2024, 1, 15)


# ===========================================================================
# 23. ERROR HANDLING
# ===========================================================================

def error_handling_example(request):
    """Catch and inspect FilterValidationError and FilterValueError."""
    try:
        return FilterSet(
            queryset=Product.objects.all(),
            params=request.GET,
            allowed_fields={"price", "name"},
        ).qs

    except FilterValidationError as e:
        # e.field   — which field caused the problem
        # e.lookup  — which lookup was invalid (if any)
        # e.code    — machine-readable:
        #   "field_not_allowed"   "lookup_not_supported"  "lookup_not_allowed"
        #   "lookup_incompatible" "field_does_not_exist"  "not_a_relation"
        print(f"Validation error on '{e.field}': {e}  [code={e.code}]")
        return []

    except FilterValueError as e:
        # e.field         — field name
        # e.value         — raw value that failed conversion
        # e.expected_type — what type was expected
        # e.code          — "invalid_int" "invalid_bool" "invalid_date"
        #                   "invalid_range" "empty_list" "null_value" …
        print(f"Value error on '{e.field}': got {e.value!r}, expected {e.expected_type}  [code={e.code}]")
        return []
