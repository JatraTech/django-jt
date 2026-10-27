from django_jt.auth import Auth901UserMixin
from django_jt.mixins.models import NameModelMixin


class User(Auth901UserMixin):
    pass


class Item(NameModelMixin):
    class Meta:
        app_label = "tests"
