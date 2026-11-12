import base64
import logging
from collections.abc import Iterable
from pathlib import Path

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMessage

from django_jt.backends.email.celery import dispatch_async, should_queue_email_tasks
from django_jt.backends.email.recipients import apply_recipient_override
from django_jt.backends.email.tasks import send_gmail_emails


class GmailAuthError(RuntimeError):
    """Gmail OAuth credentials are missing or invalid."""


class GmailBackend(BaseEmailBackend):
    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
    CLIENT_SECRET_PATH = ".secrets/google_client_secret.json"
    TOKEN_PATH = ".secrets/google_token.json"

    @classmethod
    def get_client_secret_path(cls) -> Path:
        path = Path(cls.CLIENT_SECRET_PATH)
        if not path.is_absolute():
            path = settings.BASE_DIR / path
        return path

    @classmethod
    def get_token_path(cls) -> Path:
        path = Path(cls.TOKEN_PATH)
        if not path.is_absolute():
            path = settings.BASE_DIR / path
        return path

    @classmethod
    def save_credentials(cls, creds) -> Path:
        token_path = cls.get_token_path()
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        return token_path

    @classmethod
    def authenticate(cls):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        token_path = cls.get_token_path()
        if not token_path.is_file():
            raise GmailAuthError(
                f"Gmail OAuth token not found at {token_path}. "
                "Run `python manage.py gmail_oauth_token` to sign in."
            )

        creds = Credentials.from_authorized_user_file(str(token_path), cls.SCOPES)

        if creds.valid:
            return creds

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            cls.save_credentials(creds)
            logging.info("Gmail OAuth access token refreshed.")
            return creds

        raise GmailAuthError(
            f"Gmail OAuth token at {token_path} is invalid and could not be refreshed. "
            "Re-run `python manage.py gmail_oauth_token`."
        )

    @classmethod
    def get_gmail_service(cls):
        from googleapiclient.discovery import build

        try:
            creds = cls.authenticate()
            return build("gmail", "v1", credentials=creds, cache_discovery=False)
        except Exception as e:
            logging.error(f"Failed to get Gmail service: {e}")
            raise

    @classmethod
    def send_batch_emails(
        cls,
        email_messages: list[EmailMessage],
        *,
        fail_silently: bool = False,
    ) -> int:
        if not email_messages:
            return 0

        from googleapiclient.http import BatchHttpRequest

        batch = BatchHttpRequest(batch_uri="https://www.googleapis.com/batch/gmail/v1")
        service = cls.get_gmail_service()

        for email_message in email_messages:
            apply_recipient_override(email_message)
            raw_bytes = email_message.message().as_bytes()
            raw_base64 = base64.urlsafe_b64encode(raw_bytes).decode()
            message = {"raw": raw_base64}
            batch.add(service.users().messages().send(userId="me", body=message))

        try:
            batch.execute()
        except Exception:
            logging.exception("Gmail batch send failed")
            if not fail_silently:
                raise
            return 0

        return len(email_messages)

    def send_messages(self, email_messages: Iterable[EmailMessage]) -> int:
        messages = list(email_messages)
        if not messages:
            return 0
        if should_queue_email_tasks():
            dispatch_async(
                send_gmail_emails,
                messages,
                fail_silently=self.fail_silently,
            )
            return len(messages)

        return send_gmail_emails(messages, fail_silently=self.fail_silently)
