from django.contrib.auth.models import AbstractUser
from django.db import models


class AbstractExtraUser(AbstractUser):
    """Username-login user with an Auth901 subject (``auth901_sub``).

    Host projects subclass this and set ``AUTH_USER_MODEL``.
    """

    auth901_sub = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        editable=False,
        db_index=True,
        help_text="The unique identifier for the user in the Auth901 system",
    )

    class Meta(AbstractUser.Meta):
        abstract = True
