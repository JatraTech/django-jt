from django import template

from django_jt.admin_login import backstage_available

register = template.Library()


@register.simple_tag
def django_jt_backstage_installed() -> bool:
    return backstage_available()
