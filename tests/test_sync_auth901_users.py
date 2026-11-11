import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from django_jt.auth.auth901_sync import SyncOutcome, SyncPasswordOptions, sync_user

User = get_user_model()


class _Reply:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _mock_auth_remote_id(monkeypatch, *, remote_id: str):
    """Always return one Casdoor user with the given id."""

    def post(url, **kwargs):
        if "access_token" in url:
            return _Reply({"access_token": "tok"})
        return _Reply({"status": "ok", "data": "Affected"})

    def get(url, **kwargs):
        params = kwargs.get("params") or {}
        email = params.get("value") or "ada@example.com"
        return _Reply({"status": "ok", "data": [{"id": remote_id, "email": email}]})

    monkeypatch.setattr("django_jt.auth.auth901_sync.requests.post", post)
    monkeypatch.setattr(
        "django_jt.auth.auth901_sync.requests.request",
        lambda method, url, **kw: get(url, **kw) if method == "GET" else post(url, **kw),
    )


def _mock_auth(monkeypatch, *, existing: bool, remote_password: str = "***"):
    """existing=True: get-users always returns one user; else empty then after add-user returns user."""
    lookups = {"n": 0, "get_calls": 0, "add_user_posts": [], "update_user_posts": []}

    def post(url, **kwargs):
        if "access_token" in url:
            return _Reply({"access_token": "tok"})
        if "add-user" in url:
            lookups["add_user_posts"].append(kwargs.get("json") or {})
            return _Reply({"status": "ok", "data": "Affected"})
        if "update-user" in url:
            lookups["update_user_posts"].append(kwargs.get("json") or {})
            return _Reply({"status": "ok", "data": "Affected"})
        return _Reply({"status": "ok", "data": "Affected"})

    def get(url, **kwargs):
        lookups["get_calls"] += 1
        lookups["n"] += 1
        params = kwargs.get("params") or {}
        email = params.get("value") or "ada@example.com"
        if existing:
            return _Reply(
                {
                    "status": "ok",
                    "data": [
                        {
                            "id": "remote-sub-1",
                            "email": email,
                            "owner": "built-in",
                            "name": "ada",
                            "password": remote_password,
                        }
                    ],
                }
            )
        if lookups["n"] == 1:
            return _Reply({"status": "ok", "data": []})
        return _Reply(
            {
                "status": "ok",
                "data": [
                    {
                        "id": "new-sub-1",
                        "email": email,
                        "owner": "built-in",
                        "name": "ada",
                        "password": "",
                    }
                ],
            }
        )

    monkeypatch.setattr("django_jt.auth.auth901_sync.requests.post", post)
    monkeypatch.setattr(
        "django_jt.auth.auth901_sync.requests.request",
        lambda method, url, **kw: get(url, **kw) if method == "GET" else post(url, **kw),
    )
    return lookups


@pytest.mark.django_db
def test_sync_skips_when_auth901_sub_set():
    user = User.objects.create_user(
        username="ada",
        email="ada@example.com",
        password="x",
        auth901_sub="already",
    )
    assert sync_user(user) == SyncOutcome.SKIPPED_LINKED


@pytest.mark.django_db
def test_sync_skips_without_email():
    user = User.objects.create_user(username="noname", email="", password="x")
    assert sync_user(user) == SyncOutcome.SKIPPED_NO_EMAIL


@pytest.mark.django_db
def test_sync_links_existing_auth901_user(monkeypatch):
    counters = _mock_auth(monkeypatch, existing=True)
    user = User.objects.create_user(username="ada", email="ada@example.com", password="x")
    assert sync_user(user) == SyncOutcome.LINKED_EXISTING
    user.refresh_from_db()
    assert user.auth901_sub == "remote-sub-1"
    assert counters["get_calls"] == 1
    assert counters["add_user_posts"] == []


@pytest.mark.django_db
def test_sync_creates_then_links(monkeypatch):
    counters = _mock_auth(monkeypatch, existing=False)
    user = User.objects.create_user(username="ada", email="ada@example.com", password="x")
    assert sync_user(user) == SyncOutcome.CREATED
    user.refresh_from_db()
    assert user.auth901_sub == "new-sub-1"
    assert counters["get_calls"] == 2
    assert len(counters["add_user_posts"]) == 1
    assert counters["add_user_posts"][0]["name"] == "ada"


@pytest.mark.django_db
def test_sync_create_uses_django_username_not_email_local(monkeypatch):
    counters = _mock_auth(monkeypatch, existing=False)
    user = User.objects.create_user(
        username="sanaullah",
        email="srrabbi01@gmail.com",
        first_name="Sanaullah",
        last_name="Rabbi",
        password="x",
    )
    assert sync_user(user) == SyncOutcome.CREATED
    payload = counters["add_user_posts"][0]
    assert payload["name"] == "sanaullah"
    assert payload["firstName"] == "Sanaullah"
    assert payload["lastName"] == "Rabbi"
    assert payload["displayName"] == "Sanaullah Rabbi"


@pytest.mark.django_db
def test_sync_uses_name_field_when_no_first_last(monkeypatch):
    counters = _mock_auth(monkeypatch, existing=False)
    user = User.objects.create_user(username="sanaullah", email="srrabbi01@gmail.com", password="x")
    user.name = "Sanaullah Rabbi"
    assert sync_user(user) == SyncOutcome.CREATED
    payload = counters["add_user_posts"][0]
    assert payload["name"] == "sanaullah"
    assert payload["firstName"] == "Sanaullah"
    assert payload["lastName"] == "Rabbi"
    assert payload["displayName"] == "Sanaullah Rabbi"


@pytest.mark.django_db
def test_dry_run_does_not_persist(monkeypatch):
    _mock_auth(monkeypatch, existing=False)
    user = User.objects.create_user(username="ada", email="ada@example.com", password="x")
    assert sync_user(user, dry_run=True) == SyncOutcome.CREATED
    user.refresh_from_db()
    assert user.auth901_sub is None


@pytest.mark.django_db
def test_management_command_skips_inactive_by_default(monkeypatch, capsys):
    _mock_auth(monkeypatch, existing=True)
    User.objects.create_user(
        username="off",
        email="off@example.com",
        password="x",
        is_active=False,
    )
    call_command("sync_auth901_users")
    out = capsys.readouterr().out
    assert "off@example.com" not in out


@pytest.mark.django_db
def test_management_command_include_inactive(monkeypatch, capsys):
    _mock_auth(monkeypatch, existing=True)
    User.objects.create_user(
        username="off",
        email="off@example.com",
        password="x",
        is_active=False,
    )
    call_command("sync_auth901_users", include_inactive=True)
    out = capsys.readouterr().out
    assert "off@example.com" in out
    assert User.objects.get(email="off@example.com").auth901_sub == "remote-sub-1"


@pytest.mark.django_db
def test_repair_relinks_when_remote_id_differs(monkeypatch):
    _mock_auth_remote_id(monkeypatch, remote_id="remote-sub-2")
    user = User.objects.create_user(
        username="ada",
        email="ada@example.com",
        password="x",
        auth901_sub="stale-sub",
    )
    assert sync_user(user, repair=True) == SyncOutcome.RELINKED
    user.refresh_from_db()
    assert user.auth901_sub == "remote-sub-2"


@pytest.mark.django_db
def test_repair_skipped_when_remote_matches_local_sub(monkeypatch):
    _mock_auth_remote_id(monkeypatch, remote_id="same-sub")
    user = User.objects.create_user(
        username="ada",
        email="ada@example.com",
        password="x",
        auth901_sub="same-sub",
    )
    assert sync_user(user, repair=True) == SyncOutcome.SKIPPED_LINKED
    user.refresh_from_db()
    assert user.auth901_sub == "same-sub"


@pytest.mark.django_db
def test_repair_recreates_when_remote_missing(monkeypatch):
    counters = _mock_auth(monkeypatch, existing=False)
    user = User.objects.create_user(
        username="ada",
        email="ada@example.com",
        password="x",
        auth901_sub="deleted-in-idp",
    )
    assert sync_user(user, repair=True) == SyncOutcome.RECREATED
    user.refresh_from_db()
    assert user.auth901_sub == "new-sub-1"
    assert counters["get_calls"] >= 2


@pytest.mark.django_db
def test_repair_dry_run_does_not_persist(monkeypatch):
    _mock_auth_remote_id(monkeypatch, remote_id="other-sub")
    user = User.objects.create_user(
        username="ada",
        email="ada@example.com",
        password="x",
        auth901_sub="stale-sub",
    )
    assert sync_user(user, dry_run=True, repair=True) == SyncOutcome.RELINKED
    user.refresh_from_db()
    assert user.auth901_sub == "stale-sub"


@pytest.mark.django_db
def test_command_repair_flag(monkeypatch, capsys):
    _mock_auth_remote_id(monkeypatch, remote_id="remote-sub-1")
    User.objects.create_user(
        username="ada",
        email="ada@example.com",
        password="x",
        auth901_sub="stale",
    )
    call_command("sync_auth901_users", repair=True)
    out = capsys.readouterr().out
    assert "ada@example.com: relinked" in out
    assert User.objects.get(email="ada@example.com").auth901_sub == "remote-sub-1"


@pytest.mark.django_db
def test_sync_create_includes_initial_password(monkeypatch):
    counters = _mock_auth(monkeypatch, existing=False)
    user = User.objects.create_user(username="ada", email="ada@example.com", password="x")
    opts = SyncPasswordOptions(
        initial_password="dev-secret",
        require_password_change=True,
    )
    assert sync_user(user, password_options=opts) == SyncOutcome.CREATED
    payload = counters["add_user_posts"][0]
    assert payload["password"] == "dev-secret"
    assert payload["needUpdatePassword"] is True


@pytest.mark.django_db
def test_sync_links_existing_without_password_update(monkeypatch):
    counters = _mock_auth(monkeypatch, existing=True, remote_password="")
    user = User.objects.create_user(username="ada", email="ada@example.com", password="x")
    opts = SyncPasswordOptions(initial_password="dev-secret")
    assert sync_user(user, password_options=opts) == SyncOutcome.LINKED_EXISTING
    assert counters["update_user_posts"] == []
    assert counters["add_user_posts"] == []


@pytest.mark.django_db
def test_auth901_sync_initial_password_env_wins(monkeypatch, settings):
    from django_jt.auth.base import auth901_sync_initial_password

    settings.AUTH901_SYNC_INITIAL_PASSWORD = "from-env"
    assert auth901_sync_initial_password(cli_value="from-cli") == "from-env"


@pytest.mark.django_db
def test_command_requires_service_credentials(settings, monkeypatch):
    monkeypatch.delenv("AUTH901_SERVICE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AUTH901_SERVICE_CLIENT_SECRET", raising=False)
    settings.AUTH901_SERVICE_CLIENT_ID = ""
    settings.AUTH901_SERVICE_CLIENT_SECRET = ""
    import tests.settings as test_settings

    monkeypatch.setattr(test_settings, "AUTH901_SERVICE_CLIENT_ID", "")
    monkeypatch.setattr(test_settings, "AUTH901_SERVICE_CLIENT_SECRET", "")
    with pytest.raises(CommandError):
        call_command("sync_auth901_users")


@pytest.mark.django_db
def test_command_requires_organization(settings, monkeypatch):
    monkeypatch.delenv("AUTH901_ORGANIZATION", raising=False)
    monkeypatch.delenv("AUTH901_ORGANIZATION_ID", raising=False)
    settings.AUTH901_ORGANIZATION = ""
    import tests.settings as test_settings

    monkeypatch.setattr(test_settings, "AUTH901_ORGANIZATION", "")
    with pytest.raises(CommandError, match="AUTH901_ORGANIZATION"):
        call_command("sync_auth901_users")
