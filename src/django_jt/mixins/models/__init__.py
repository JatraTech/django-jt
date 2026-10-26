from collections.abc import Iterable

from django.db import models
from django_userforeignkey.models.fields import UserForeignKey

from django_jt.mixins.models.address import AddressFields, PackAttributes
from django_jt.mixins.models.constants import ActivityStatusChoices
from django_jt.mixins.models.fields import StatusField

__all__ = [
    "ActivityStatusChoices",
    "AddressFields",
    "CodeModelManager",
    "CodeModelMixin",
    "ModelManager",
    "ModelMixin",
    "ModelQuerySet",
    "NameModelMixin",
    "PackAttributes",
    "StatusField",
]


class ModelQuerySet(models.QuerySet):
    def all_active(self):
        return self.filter(is_active=True)

    def all_inactive(self):
        return self.filter(is_active=False)


class ModelManager(models.Manager):
    queryset_class: type[ModelQuerySet] = ModelQuerySet

    def get_queryset(self):
        return self.queryset_class(self.model, using=self._db)

    def all_active(self):
        return self.get_queryset().all_active()

    def all_inactive(self):
        return self.get_queryset().all_inactive()


class CodeModelManager(ModelManager):
    def get_queryset(self):
        return super().get_queryset().annotate(_full_code=models.Value("FULL_CODE"))

    def bulk_create(self, objs: Iterable, global_code: bool = True, *args, **kwargs) -> list:
        latest_code = 0
        if global_code:
            if latest_code_obj := self.model.get_latest_code_qs().first():
                latest_code = latest_code_obj.get("code", 0)

        for obj in objs:
            obj.code = latest_code + 1
            latest_code += 1
        return super().bulk_create(
            objs,
            *args,
            **kwargs,
        )


class ModelMixin(models.Model):
    created_by = UserForeignKey(
        auto_user_add=True,
        null=True,
        blank=True,
        related_name="%(class)s_created_by",
    )  # type: ignore
    updated_by = UserForeignKey(
        auto_user=True,
        null=True,
        blank=True,
        related_name="%(class)s_updated_by",
    )  # type: ignore
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )
    is_active = models.BooleanField(default=True)

    objects: ModelManager = ModelManager()

    class Meta:
        abstract = True
        ordering = ["-id"]

    def __str__(self) -> str:
        return getattr(self, "name", super().__str__())

    @classmethod
    def get_choice_fields(cls):
        return [i.name for i in cls._meta.get_fields() if hasattr(i, "choices") and i.choices]


class NameModelMixin(ModelMixin):
    name = models.CharField(max_length=255)

    class Meta:
        abstract = True
        ordering = ["-id"]

    def __str__(self) -> str:
        return self.name[:30]


class CodeModelMixin(ModelMixin):
    code_prefix = ""
    zfill_width = 3
    code = models.BigIntegerField(unique=True, editable=False)

    objects: CodeModelManager = CodeModelManager()

    class Meta:
        abstract = True
        ordering = ["-id"]

    @classmethod
    def get_latest_code_qs(
        cls,
    ):
        """
        returns the queryset of latest code, so that filters can be applied in subclasses if necessary
        """
        return cls.objects.order_by("-code").values("code")

    def generate_code(self):
        latest_code = 0
        if latest_entry := self.get_latest_code_qs().first():
            latest_code = latest_entry.get("code", 0)
        return latest_code + 1

    def save(
        self,
        *args,
        force_insert=False,
        force_update=False,
        using=None,
        update_fields=None,
        **kwargs,
    ) -> None:
        if not self.pk:
            self.code = self.generate_code()
        return super().save(
            *args,
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    @property
    def full_code(self) -> str:
        full_code = str(self.code).zfill(self.zfill_width)
        if self.code_prefix:
            full_code = f"{self.code_prefix}-{full_code}"
        return full_code
