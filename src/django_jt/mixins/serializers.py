from rest_framework import serializers
from rest_framework.fields import empty
from rest_framework.serializers import Field, ModelSerializer

from django_jt.mixins.models import CodeModelMixin, ModelMixin


class BaseModelSerializer(ModelSerializer):
    always_exclude_fields = (
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "deleted_at",
        "is_active",
    )

    class Meta:
        ignore_always_exclude_fields = []

    def get_field_names(self, declared_fields, info):
        fields = super().get_field_names(declared_fields, info)
        excluded_fields = (
            set(self.always_exclude_fields) - set(self.Meta.ignore_always_exclude_fields)
            if getattr(self.Meta, "ignore_always_exclude_fields", None)
            else self.always_exclude_fields
        )
        return [f for f in fields if f not in excluded_fields]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if isinstance(instance, CodeModelMixin):
            data["full_code"] = instance.full_code
        if isinstance(instance, ModelMixin):
            for i in self.Meta.model.get_choice_fields():
                data[f"{i}_display"] = getattr(instance, f"get_{i}_display")()
        return data


class ExtendableModelSerializer(BaseModelSerializer):
    extend_field_serializers = {}

    def __init__(self, instance=None, data=empty, **kwargs):
        super().__init__(instance, data, **kwargs)
        for i in self.context.get("extendable_fields", []):
            field: Field = self.extend_field_serializers[i]
            if field.source == i:
                field.source = None
            self.fields.update(**{i: field})


class URLSerializer(serializers.Serializer):
    url = serializers.URLField()
