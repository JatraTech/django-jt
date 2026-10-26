from typing import Any

from django.db.models import IntegerField

from django_jt.mixins.models.constants import ActivityStatusChoices


class StatusField(IntegerField):
    description = "Item's availability status"

    def __init__(self, default=ActivityStatusChoices.ACTIVE, *args: Any, **kwargs: Any) -> None:
        kwargs["default"] = default
        kwargs["choices"] = ActivityStatusChoices.choices
        super().__init__(*args, **kwargs)
