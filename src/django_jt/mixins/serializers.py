import re
from urllib.parse import urlparse

from django.conf import settings
from django.db.models import FileField, ImageField
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
        request = self.context.get("request")

        if self.Meta.model:
            for field in self.Meta.model._meta.get_fields():
                field_name = field.name
                if field_name not in data or not isinstance(field, (ImageField, FileField)):
                    continue
                field_value = getattr(instance, field_name, None)
                data[field_name] = get_image_url(request, field_value)

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


def get_image_url(request, file_field) -> str | None:
    if not file_field:
        return None
    try:
        url = file_field.url
    except (ValueError, AttributeError):
        return None

    if urlparse(url).scheme in ("http", "https"):
        return url

    if request:
        return request.build_absolute_uri(url)

    return f"http://localhost:8000{url}" if settings.DEBUG else url


MEDIA_SRC_PATTERN = re.compile(r'src="(/media/[^"]+)"')


def resolve_content_media_urls(html: str, request) -> str:
    if not html or not request:
        return html

    return MEDIA_SRC_PATTERN.sub(
        lambda match: f'src="{request.build_absolute_uri(match.group(1))}"',
        html,
    )


def resolve_rich_text_fields(data: dict, fields: list[str], request) -> dict:
    for name in fields:
        if data.get(name):
            data[name] = resolve_content_media_urls(data[name], request)
    return data
