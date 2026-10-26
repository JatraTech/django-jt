from decimal import Decimal
from typing import Any

from django.db import models
from django.db.models import DecimalField

from django_jt.crypto import decrypt_json, decrypt_str, encrypt_json, encrypt_str


class MoneyField(DecimalField):
    """Template money field. Prefer AmountField / UnitPriceField below."""

    def __init__(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        kwargs["decimal_places"] = kwargs.pop("decimal_places", 2)
        kwargs["max_digits"] = kwargs.pop("max_digits", 10)
        kwargs["default"] = kwargs.pop("default", Decimal(0))
        super().__init__(*args, **kwargs)


class AmountField(MoneyField):
    """Totals, balances, payments: 2 decimals, up to 999,999,999,999.99."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_digits", 14)
        kwargs.setdefault("decimal_places", 2)
        super().__init__(*args, **kwargs)


class UnitPriceField(MoneyField):
    """Unit prices and costs: 4 decimals, for per-square-foot and per-linear-foot pricing."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_digits", 14)
        kwargs.setdefault("decimal_places", 4)
        super().__init__(*args, **kwargs)


class QuantityField(DecimalField):
    """Quantities with units (2.5 squares, 120 linear feet, 0.75 hours)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_digits", 12)
        kwargs.setdefault("decimal_places", 3)
        kwargs.setdefault("default", Decimal("1"))
        super().__init__(*args, **kwargs)


class EncryptedTextField(models.TextField):
    """Stores Fernet-encrypted text; reads back plain text. Not searchable."""

    def from_db_value(self, value, expression, connection):
        return decrypt_str(value) if value else ""

    def to_python(self, value):
        return value if value is not None else ""

    def get_prep_value(self, value):
        return encrypt_str(value or "")


class EncryptedJSONField(models.TextField):
    """Stores a Fernet-encrypted JSON document; reads back the Python object. Not searchable."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("default", dict)
        kwargs.setdefault("blank", True)
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        return decrypt_json(value) if value else {}

    def to_python(self, value):
        if isinstance(value, (dict, list)):
            return value
        if not value:
            return {}
        return value

    def get_prep_value(self, value):
        return encrypt_json(value or {})

    def value_to_string(self, obj):  # serialization (dumpdata) never emits plaintext
        return self.get_prep_value(self.value_from_object(obj))
