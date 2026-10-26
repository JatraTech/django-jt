from django.urls import include, path

from django_jt.auth.views import InviteMemberView

urlpatterns = [
    path("oidc/", include("mozilla_django_oidc.urls")),
    path("auth/invite/", InviteMemberView.as_view(), name="auth901-invite"),
]
