# django-filterly — Zero-Boilerplate Filtering for Django

![PyPI](https://img.shields.io/pypi/v/django-filterly)
![Coverage](https://img.shields.io/badge/coverage-99%25-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)

> **A clean, flexible Django queryset filtering library driven by query-string params.**  
> Drop it into any Django or DRF view and turn URL parameters into ORM queries — zero boilerplate.

---

## ⚡ What You Get

```
GET /products?name__icontains=shirt&price__gte=100&is_active=true
```

```python
from django_filterly import FilterSet

def product_list(request):
    qs = FilterSet(
        queryset=Product.objects.all(),
        params=request.GET,
    ).qs
    return JsonResponse(list(qs.values()), safe=False)

# Equivalent to:
# Product.objects.filter(name__icontains="shirt")
#                .filter(price__gte=100)
#                .filter(is_active=True)
```

That's it — no manual parsing, no type casting, no repetitive `if "field" in request.GET` blocks.

---

## 🚀 Key Features

- **Zero-Boilerplate Filtering** from query params — no manual parsing
- **Automatic Type Coercion** — bool, int, float, date, datetime, list, range, UUID
- **Deep Relation Filtering** — `user__profile__city__icontains=Cairo`
- **Built-In Validation** with structured errors and machine-readable codes
- **Works With Django & DRF** out of the box — no extra setup
- **No Config, No Magic Classes** — just pass `request.GET` and go

---

## ✨ Why django-filterly?

| Without filterly | With filterly |
|---|---|
| Parse `request.GET` by hand | One `FilterSet(queryset, request.GET).qs` call |
| Write repetitive `if "field" in request.GET` blocks | Automatic type coercion, validation, and ORM mapping |
| Risk invalid values crashing your queries | Structured errors with machine-readable codes |
| Duplicate filter logic across views | Reusable `FilterSet` subclasses per model |

---

## 🤔 Why not django-filter?

- **No serializers required** — pass `request.GET` directly, no `FilterSet` class declaration needed
- **No config-heavy classes** — no `Meta`, no `fields = [...]`, no per-field `Filter()` instances
- **Works directly with query params** — drop it into any view or script with a plain dict
- **Zero setup** — no `INSTALLED_APPS` entry, no migration, no wiring

---

## 📦 Installation

```bash
pip install django-filterly
```

No extra settings needed — filterly has zero Django app registration. Just import and use.

> **Requirements:** Python ≥ 3.8 · Django ≥ 3.2

---

## 🔍 Supported Lookups

### Text / String

| Lookup | SQL equivalent | Example param |
|---|---|---|
| `exact` | `= 'value'` | `name__exact=T-Shirt` |
| `iexact` | `ILIKE 'value'` | `name__iexact=t-shirt` |
| `contains` | `LIKE '%value%'` | `name__contains=shirt` |
| `icontains` | `ILIKE '%value%'` | `name__icontains=shirt` |
| `startswith` | `LIKE 'value%'` | `name__startswith=T` |
| `istartswith` | `ILIKE 'value%'` | `name__istartswith=t` |
| `endswith` | `LIKE '%value'` | `name__endswith=Shirt` |
| `iendswith` | `ILIKE '%value'` | `name__iendswith=shirt` |
| `regex` | `~ 'pattern'` | `name__regex=^T.*t$` |
| `iregex` | `~* 'pattern'` | `name__iregex=^t.*t$` |

### Comparison

| Lookup | SQL equivalent | Example param |
|---|---|---|
| `gt` | `> value` | `price__gt=50` |
| `gte` | `>= value` | `price__gte=50` |
| `lt` | `< value` | `price__lt=200` |
| `lte` | `<= value` | `price__lte=200` |

### Date & Time Parts

| Lookup | Extracts | Example param |
|---|---|---|
| `date` | Date part of a datetime | `created_at__date=2024-01-15` |
| `year` | Year integer | `created_at__year=2024` |
| `month` | Month integer (1–12) | `created_at__month=6` |
| `day` | Day integer (1–31) | `created_at__day=15` |
| `week` | ISO week number | `created_at__week=3` |
| `week_day` | 1=Sun … 7=Sat | `created_at__week_day=2` |
| `hour` | Hour (0–23) | `updated_at__hour=14` |
| `minute` | Minute (0–59) | `updated_at__minute=30` |
| `second` | Second (0–59) | `updated_at__second=0` |

### Sets & Ranges

| Lookup | Behaviour | Example param |
|---|---|---|
| `in` | Field value is one of a list | `status__in=active,pending,review` |
| `range` | BETWEEN two values (inclusive) | `price__range=10,500` |

### Null / Existence

| Lookup | Behaviour | Example param |
|---|---|---|
| `isnull` | IS NULL / IS NOT NULL | `deleted_at__isnull=true` |

### Exclusion (NOT)

| Lookup | Behaviour | Example param |
|---|---|---|
| `not` | `.exclude(field__exact=value)` | `status__not=draft` |

### JSON Fields (PostgreSQL)

| Lookup | Behaviour | Example param |
|---|---|---|
| `contains` | JSON subset match | `meta__contains={"color":"red"}` |
| `has_key` | Key exists | `meta__has_key=color` |
| `has_keys` | All keys present | `meta__has_keys=color,size` |
| `has_any_keys` | Any key present | `meta__has_any_keys=color,size` |

### Array Fields (PostgreSQL)

| Lookup | Behaviour | Example param |
|---|---|---|
| `contains` | Array contains all values | `tags__contains=sale,new` |
| `overlap` | Array shares ≥1 value | `tags__overlap=sale,promo` |
| `len` | Array length equals N | `tags__len=3` |

---

## 📖 Usage Examples

### 1. Plain dict — useful in tests or scripts

```python
qs = FilterSet(
    queryset=Product.objects.all(),
    params={"price__gte": "50", "is_active": "true"},
).qs
```

### 2. Boolean values

filterly accepts any of these for `True` / `False`:

```
true  1  yes  on   → True
false 0  no   off  → False
```

### 3. Null checks

```
?deleted_at__isnull=true   → WHERE deleted_at IS NULL
?deleted_at__isnull=false  → WHERE deleted_at IS NOT NULL
```

### 4. Exclude / NOT

```
?status__not=draft  →  .exclude(status__exact="draft")
```

### 5. IN queries — two syntaxes

```
# Comma-separated string
?status__in=active,pending,review

# Multi-value QueryDict (?status=active&status=pending)
# auto-promoted to __in when the same key appears multiple times
```

### 6. Range queries

```
?price__range=10,500              → WHERE price BETWEEN 10 AND 500
?created_at__range=2024-01-01,2024-12-31
```

### 7. Date & datetime

```
?created_at__date=2024-01-15
?created_at__year=2024
?created_at__gte=2024-01-01T00:00:00
?created_at__lte=2024-12-31T23:59:59Z   ← Z suffix handled
```

### 8. Foreign key traversal — ORM style

```
?owner__email__icontains=gmail.com
?user__age__gte=18
```

### 9. Foreign key traversal — flat shorthand

Three or more underscore-separated segments where the last is a known lookup:

```
?owner_email_icontains=gmail.com   →  owner__email__icontains
?user_age_gte=18                   →  user__age__gte
```

Plain two-segment fields (`is_active`, `created_at`, `user_id`) are **not** treated as flat notation.

### 10. Deep / multi-hop relations

```
?owner__profile__city__icontains=Cairo
```

### 11. JSON field lookups

```
?meta__has_key=color
?meta__has_keys=color,size
?meta__has_any_keys=color,size
?meta__contains={"color": "red"}
```

### 12. PostgreSQL array field lookups

```
?tags__contains=sale,new
?tags__overlap=sale,promo
?tags__len=3
```

### 13. Custom transformers — per-field value conversion

```python
def parse_price(value, *, field, lookup):
    cleaned = str(value).lstrip("$€£").strip()
    try:
        return float(cleaned)
    except ValueError:
        raise FilterValueError(
            f"Cannot parse '{value}' as a price.",
            field=field, lookup=lookup, value=value,
            expected_type="float", code="invalid_price",
        )

qs = FilterSet(
    queryset=Product.objects.all(),
    params={"price__gte": "$100.00"},
    custom_transformers={"price": parse_price},
).qs
```

### 14. DRF — inside a ListAPIView

```python
from rest_framework.generics import ListAPIView
from django_filterly import FilterSet

class ProductListView(ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        qs = FilterSet(
            queryset=Product.objects.all(),
            params=self.request.GET,
            allowed_fields={"name", "price", "is_active", "created_at"},
            allowed_lookups={"exact", "icontains", "gte", "lte", "range"},
        ).qs
        return qs
```

### 15. Subclassing FilterSet — reusable defaults per model

```python
class ProductFilterSet(FilterSet):
    _FIELDS = {
        "name", "price", "stock", "is_active",
        "created_at", "updated_at", "owner__email",
    }
    _LOOKUPS = {
        "exact", "icontains", "gt", "gte", "lt", "lte",
        "range", "in", "isnull", "not", "year", "month",
    }

    def __init__(self, params, *, queryset=None, **kwargs):
        super().__init__(
            queryset=queryset or Product.objects.all(),
            params=params,
            allowed_fields=kwargs.pop("allowed_fields", self._FIELDS),
            allowed_lookups=kwargs.pop("allowed_lookups", self._LOOKUPS),
            **kwargs,
        )

# In a view:
qs = ProductFilterSet(request.GET).qs
```

---

## 🔧 Advanced Usage (Validation, Whitelisting, Errors)

### Whitelisting fields and lookups

`allowed_fields` and `allowed_lookups` are **optional**.

- **Omit them** → filterly accepts any field that exists on the model and any supported lookup. Good for internal tools or trusted clients.
- **Set them** → filterly rejects anything outside the whitelist with a `FilterValidationError`. Use this in public APIs to prevent callers from filtering on sensitive fields (e.g. `password`, `secret_token`) or using expensive lookups (e.g. `regex`).

```python
# No whitelist — all model fields and all supported lookups accepted
qs = FilterSet(
    queryset=Product.objects.all(),
    params=request.GET,
).qs

# With whitelist — anything outside raises FilterValidationError
qs = FilterSet(
    queryset=Product.objects.all(),
    params=request.GET,
    allowed_fields={"price", "status", "created_at"},   # only these fields
    allowed_lookups={"exact", "gte", "lte", "in"},      # only these lookups
).qs
```

### Full example with error handling

```python
from django_filterly import FilterSet, FilterValidationError, FilterValueError

def product_list(request):
    """
    Examples:
    ?name__icontains=shirt
    ?price__range=10,500
    ?is_active=true
    ?created_at__year=2024
    ?status__in=active,pending
    ?deleted_at__isnull=true
    ?status__not=draft
    ?owner__email__icontains=gmail
    """
    try:
        qs = FilterSet(
            queryset=Product.objects.select_related("owner").all(),
            params=request.GET,
            allowed_fields={"name", "price", "is_active", "status",
                            "created_at", "deleted_at", "owner__email"},
            allowed_lookups={"exact", "icontains", "gte", "lte", "range",
                             "in", "isnull", "not", "year"},
        ).qs
        return JsonResponse(list(qs.values()), safe=False)

    except FilterValidationError as e:
        # e.field, e.lookup, e.code  →  "field_not_allowed" | "lookup_incompatible" | …
        return HttpResponseBadRequest(str(e))

    except FilterValueError as e:
        # e.field, e.value, e.expected_type, e.code  →  "invalid_int" | "invalid_date" | …
        return HttpResponseBadRequest(str(e))
```

### Error codes reference

| Code | Exception | When raised |
|---|---|---|
| `field_not_allowed` | `FilterValidationError` | Field not in `allowed_fields` |
| `lookup_not_supported` | `FilterValidationError` | Lookup unknown to filterly |
| `lookup_not_allowed` | `FilterValidationError` | Lookup not in `allowed_lookups` |
| `lookup_incompatible` | `FilterValidationError` | Lookup wrong for field's data type |
| `field_does_not_exist` | `FilterValidationError` | Field not on the model |
| `not_a_relation` | `FilterValidationError` | FK traversal on a non-FK field |
| `invalid_bool` | `FilterValueError` | Value not a recognised boolean |
| `invalid_int` | `FilterValueError` | Value not a valid integer |
| `invalid_float` | `FilterValueError` | Value not a valid float |
| `invalid_number` | `FilterValueError` | Value not a valid number |
| `invalid_date` | `FilterValueError` | Value not ISO 8601 date |
| `invalid_datetime` | `FilterValueError` | Value not ISO 8601 datetime |
| `invalid_time` | `FilterValueError` | Value not a valid time |
| `invalid_uuid` | `FilterValueError` | Value not a valid UUID |
| `invalid_range` | `FilterValueError` | Range does not have exactly 2 values |
| `empty_list` | `FilterValueError` | `__in` list is empty |
| `null_value` | `FilterValueError` | `None` passed for a non-nullable field |

---

## 🛒 Real Example (E-commerce)

A shopper hits this URL:

```
GET /products?price__gte=100&price__lte=500&is_active=true&category__name__icontains=shoes&stock__gt=0&created_at__year=2024&tags__overlap=sale,new&ordering=price
```

filterly handles all 7 filter params in one call:

```python
from django_filterly import FilterSet, FilterValidationError, FilterValueError
from django.http import JsonResponse, HttpResponseBadRequest

def product_list(request):
    try:
        qs = FilterSet(
            queryset=Product.objects.select_related("category").all(),
            params=request.GET,
            allowed_fields={
                "price", "is_active", "stock", "created_at",
                "category__name", "tags",
            },
            allowed_lookups={
                "gte", "lte", "gt", "exact",
                "icontains", "year", "overlap",
            },
        ).qs
        return JsonResponse(list(qs.values()), safe=False)

    except FilterValidationError as e:
        return HttpResponseBadRequest({"error": str(e), "field": e.field, "code": e.code})

    except FilterValueError as e:
        return HttpResponseBadRequest({"error": str(e), "field": e.field, "code": e.code})
```

What filterly does under the hood for that URL:

| Param | Parsed as | ORM call |
|---|---|---|
| `price__gte=100` | field=`price`, lookup=`gte`, value=`100.0` | `.filter(price__gte=100.0)` |
| `price__lte=500` | field=`price`, lookup=`lte`, value=`500.0` | `.filter(price__lte=500.0)` |
| `is_active=true` | field=`is_active`, lookup=`exact`, value=`True` | `.filter(is_active=True)` |
| `category__name__icontains=shoes` | field=`category__name`, lookup=`icontains` | `.filter(category__name__icontains="shoes")` |
| `stock__gt=0` | field=`stock`, lookup=`gt`, value=`0` | `.filter(stock__gt=0)` |
| `created_at__year=2024` | field=`created_at`, lookup=`year`, value=`2024` | `.filter(created_at__year=2024)` |
| `tags__overlap=sale,new` | field=`tags`, lookup=`overlap`, value=`["sale","new"]` | `.filter(tags__overlap=["sale","new"])` |

> **Note:** `ordering` is not a filter param — filterly ignores any param that doesn't match a field + lookup pattern.  
> → You can safely mix filtering with pagination, ordering, or any other custom query params in the same URL.

---

## 🛠 Low-Level API

You can use individual modules directly when you only need part of the pipeline.

### Parser only

```python
from django_filterly import parse_params

descriptors = parse_params({"price__gte": "100", "name__icontains": "shirt"})
for d in descriptors:
    print(d.field, d.lookup, d.value, d.exclude)
# price  gte        100    False
# name   icontains  shirt  False
```

### Validator only

```python
from django_filterly import FilterDescriptor, validate_filter

validate_filter(
    FilterDescriptor(field="price", lookup="gte", value="100"),
    model=Product,
    allowed_fields={"price", "name"},
    allowed_lookups={"gte", "lte", "icontains"},
)
```

### Individual transformers

```python
from django_filterly import to_bool, to_date, to_int

to_int("42",           field="age",        lookup="gte")   # → 42
to_bool("yes",         field="is_active",  lookup="exact") # → True
to_date("2024-01-15",  field="created_at", lookup="date")  # → date(2024, 1, 15)
```

---

## 🗂 Project Structure

```
django-filterly/
├── django_filterly/
│   ├── __init__.py
│   ├── constants.py      # lookup groups and type→lookup maps
│   ├── exceptions.py     # FilterValidationError, FilterValueError
│   ├── helpers.py        # field resolution and type detection
│   ├── parser.py         # FilterDescriptor + parse_params()
│   ├── transformers.py   # type coercion functions
│   ├── validators.py     # validate_filter() / validate_all()
│   └── filterset.py      # FilterSet — the main public API
├── tests/
│   └── test_filters.py
├── examples/
│   └── basic_usage.py
├── run_tests.py
└── pyproject.toml
```

---

## 🧪 Running the Tests

```bash
# Clone and set up
git clone https://github.com/esraamashaal/django-filterly.git
cd django-filterly

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

# Install dev dependencies
pip install -e ".[dev]"

# Run all tests with coverage
python run_tests.py

# Or with pytest directly
pytest tests/ -v
pytest tests/ -v --tb=short --cov=django_filterly --cov-report=term-missing

# Run a specific test class
pytest tests/ -k TestParser -v
pytest tests/ -k TestFilterSet -v
```

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

## 👩‍💻 Author

<table>
  <tr>
    <td>
      <strong>Esraa Raffik Mashaal</strong><br/>
      Senior Software Engineer<br/><br/>
      <a href="https://www.linkedin.com/in/esraamashaal/">
        <img src="https://img.shields.io/badge/LinkedIn-Esraa%20Mashaal-0077B5?style=for-the-badge&logo=linkedin&logoColor=white"/>
      </a>
    </td>
  </tr>
</table>
