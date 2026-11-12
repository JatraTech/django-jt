from django.db import models

from django_jt.auth import Auth901UserMixin
from django_jt.mixins.models import NameModelMixin


class User(Auth901UserMixin):
    pass


class Item(NameModelMixin):
    class Meta:
        app_label = "tests"


class TimedItem(models.Model):
    name = models.CharField(max_length=64)
    due_at = models.DateTimeField()

    class Meta:
        app_label = "tests"
