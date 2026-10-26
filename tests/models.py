from django_jt.auth import AbstractExtraUser
from django_jt.mixins.models import NameModelMixin


class User(AbstractExtraUser):
    pass


class Item(NameModelMixin):
    class Meta:
        app_label = "tests"
