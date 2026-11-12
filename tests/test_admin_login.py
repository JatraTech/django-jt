from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.template.loader import get_template
from django.test import RequestFactory, override_settings

from django_jt.admin_login import oidc_admin_login_templates_dir, prepend_oidc_admin_login_templates
from django_jt.checks import auth901_oidc_installed_apps

_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {},
    }
]


@override_settings(AUTH901_CLIENT_ID="cid", TEMPLATES=_TEMPLATES)
def test_prepend_oidc_admin_login_templates_idempotent():
    prepend_oidc_admin_login_templates()
    path = str(oidc_admin_login_templates_dir())
    assert path in settings.TEMPLATES[0]["DIRS"]
    n = len(settings.TEMPLATES[0]["DIRS"])
    prepend_oidc_admin_login_templates()
    assert len(settings.TEMPLATES[0]["DIRS"]) == n


@override_settings(AUTH901_CLIENT_ID="", TEMPLATES=_TEMPLATES)
def test_prepend_skipped_when_oidc_disabled():
    dirs_before = list(settings.TEMPLATES[0].get("DIRS", []))
    prepend_oidc_admin_login_templates()
    assert settings.TEMPLATES[0].get("DIRS", []) == dirs_before


@override_settings(AUTH901_CLIENT_ID="cid", TEMPLATES=_TEMPLATES)
@patch("django_jt.templatetags.django_jt_admin.backstage_available", return_value=False)
def test_stock_login_template_renders_oidc_link(_mock_backstage):
    prepend_oidc_admin_login_templates()
    request = RequestFactory().get("/admin/login/?next=/admin/")
    request.user = AnonymousUser()
    template = get_template("admin/login_oidc_stock.html")
    html = template.render(
        {
            "title": "Log in",
            "site_title": "Test Admin",
            "site_header": "Test",
            "site_name": "Test",
            "user": request.user,
            "username": "",
            "app_path": "/admin/login/",
        },
        request,
    )
    assert "oidc/authenticate" in html
    assert "id_username" not in html


@override_settings(AUTH901_CLIENT_ID="cid")
@patch("django_jt.checks.apps.is_installed", return_value=False)
def test_e002_warns_when_mozilla_not_installed(_mock_is_installed):
    warnings = auth901_oidc_installed_apps(None)
    assert len(warnings) == 1
    assert warnings[0].id == "django_jt.E002"


@override_settings(AUTH901_CLIENT_ID="")
def test_e002_silent_when_oidc_disabled():
    warnings = auth901_oidc_installed_apps(None)
    assert warnings == []
