import pytest
import requests
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


class _Reply:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.mark.django_db
def test_invite_member_creates_auth901_user(settings, monkeypatch):
    settings.AUTH901_ORGANIZATION_ID = "org-1"
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/oauth/v2/token"):
            return _Reply({"access_token": "tok"})
        return _Reply({"id": "auth901-user-1"})

    monkeypatch.setattr("django_jt.auth.oidc.requests.post", post)
    staff = User.objects.create_user(username="staff", email="staff@example.com", password="secret")
    client = APIClient()
    client.force_authenticate(staff)

    response = client.post(
        "/auth/invite/",
        {"email": "new@example.com", "given_name": "New", "family_name": "Person"},
        format="json",
    )

    assert response.status_code == 201
    assert response.json() == {"id": "auth901-user-1", "email": "new@example.com"}
    created = User.objects.get(email="new@example.com")
    assert created.auth901_sub == "auth901-user-1"
    assert created.username == "new"
    token_url, token_kwargs = calls[0]
    assert token_url.endswith("/oauth/v2/token")
    assert token_kwargs["data"]["grant_type"] == "client_credentials"
    assert token_kwargs["data"]["client_id"] == "svc"
    invite_url, invite_kwargs = calls[1]
    assert invite_url == "https://auth.new901.io/v2/users/new"
    assert invite_kwargs["headers"]["Authorization"] == "Bearer tok"
    assert invite_kwargs["json"] == {
        "username": "new@example.com",
        "organizationId": "org-1",
        "human": {
            "profile": {"givenName": "New", "familyName": "Person"},
            "email": {"email": "new@example.com", "sendCode": {}},
        },
    }


@pytest.mark.django_db
def test_invite_requires_authentication():
    response = APIClient().post(
        "/auth/invite/",
        {"email": "new@example.com", "given_name": "New", "family_name": "Person"},
        format="json",
    )
    assert response.status_code == 401


def test_invite_http_failure_is_unavailable(monkeypatch):
    def post(url, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr("django_jt.auth.oidc.requests.post", post)
    from django_jt.auth.oidc import Auth901Unavailable, invite_user

    with pytest.raises(Auth901Unavailable):
        invite_user("new@example.com", "New", "Person")
