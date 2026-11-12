from django.urls import include, path

from django_jt.auth.defaults import auth901_oidc_enabled

urlpatterns: list = []

if auth901_oidc_enabled():
    urlpatterns.append(path("oidc/", include("mozilla_django_oidc.urls")))

try:
    from django_jt.auth.views import InviteMemberView

    urlpatterns.append(path("auth/invite/", InviteMemberView.as_view(), name="auth901-invite"))
except ImportError:
    pass
