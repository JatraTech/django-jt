from unittest import mock

from django.core.mail import EmailMessage

from django_jt.backends.email.postmaster import PostMasterEmailBackend


def test_send_messages_includes_provider_hints():
    backend = PostMasterEmailBackend(fail_silently=False)
    msg = EmailMessage(
        subject="Hi",
        body="Body",
        from_email="YMCA President <president@ymcalofts.org>",
        to=["to@example.com"],
    )
    msg.provider_name = "YMCA President"

    with mock.patch.object(backend, "_post") as post:
        post.return_value.status_code = 202
        post.return_value.raise_for_status = lambda: None
        assert backend.send_messages([msg]) == 1

    payload = post.call_args[0][0]
    assert payload["provider_sender_email"] == "president@ymcalofts.org"
    assert payload["provider_name"] == "YMCA President"
