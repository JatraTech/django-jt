from django.db import models

from django_jt.fields import EncryptedJSONField


class AddressFields(models.Model):
    """A postal address. US-first, but nothing here assumes a US format."""

    address_line1 = models.CharField(max_length=255, blank=True, default="")
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=120, blank=True, default="")
    region = models.CharField("state / region", max_length=120, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="", db_index=True)
    country = models.CharField(max_length=2, blank=True, default="US")

    class Meta:
        abstract = True

    @property
    def address_text(self) -> str:
        city_line = " ".join(p for p in [f"{self.city}," if self.city else "", self.region, self.postal_code] if p)
        return ", ".join(p for p in [self.address_line1, self.address_line2, city_line.strip()] if p)


class PackAttributes(models.Model):
    """Industry-specific fields defined by the business's pack (no migrations per industry).

    ``attributes`` holds ordinary pack fields; ``sensitive_attributes`` is encrypted
    at rest and holds fields the pack marks sensitive.
    """

    attributes = models.JSONField(default=dict, blank=True)
    sensitive_attributes = EncryptedJSONField()

    class Meta:
        abstract = True
