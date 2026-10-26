from django.db.models import IntegerChoices


class ActivityStatusChoices(IntegerChoices):
    INACTIVE = (0, "Inactive")
    ACTIVE = (1, "Active")
    DRAFT = (2, "Draft")
