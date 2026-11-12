"""Django email backend that sends mail via Microsoft Graph (delegated MSAL auth)."""

from __future__ import annotations

import base64
import logging
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import msal
import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMessage, EmailMultiAlternatives

from django_jt.backends.email.celery import dispatch_async, should_queue_email_tasks
from django_jt.backends.email.recipients import apply_recipient_override
from django_jt.backends.email.tasks import send_graph_emails

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"


class GraphError(Exception):
    """Base Microsoft Graph integration error."""


class GraphConfigurationError(GraphError):
    """Graph mail is not configured."""


class GraphAuthError(GraphError):
    """Unable to acquire a Graph access token."""


class GraphSendError(GraphError):
    """Graph sendMail request failed."""


class GraphEmailBackend(BaseEmailBackend):
    SCOPES = ["Mail.Send"]
    TOKEN_CACHE_PATH = ".secrets/ms_graph_msal_cache.json"

    @classmethod
    def get_token_cache_path(cls) -> Path:
        cache_path = Path(cls.TOKEN_CACHE_PATH)
        if not cache_path.is_absolute():
            cache_path = settings.BASE_DIR / cache_path
        return cache_path

    @classmethod
    def authenticate_interactive(cls) -> str:
        return _GraphMailClient().authenticate_interactive()

    @classmethod
    def send_mail(
        cls,
        *,
        subject: str,
        body: str,
        to: Sequence[str],
        html_body: str | None = None,
    ) -> None:
        _GraphMailClient().send(
            subject=subject,
            body=body,
            to=to,
            html_body=html_body,
        )

    @classmethod
    def send_batch_emails(
        cls,
        email_messages: list[EmailMessage],
        *,
        fail_silently: bool = False,
    ) -> int:
        if not email_messages:
            return 0

        client = _GraphMailClient()
        backend = cls()
        sent_count = 0

        for message in email_messages:
            try:
                backend._send_message(client, message)
            except GraphError:
                if not fail_silently:
                    raise
            else:
                sent_count += 1

        return sent_count

    def send_messages(self, email_messages: list[EmailMessage]) -> int:
        messages = list(email_messages)
        if not messages:
            return 0

        if should_queue_email_tasks():
            dispatch_async(
                send_graph_emails,
                messages,
                fail_silently=self.fail_silently,
            )
            return len(messages)

        return send_graph_emails(messages, fail_silently=self.fail_silently)

    def _send_message(self, client: _GraphMailClient, message: EmailMessage) -> None:
        apply_recipient_override(message)

        html_body = None
        if isinstance(message, EmailMultiAlternatives):
            for content, mimetype in message.alternatives:
                if mimetype == "text/html":
                    html_body = content
                    break
        elif message.content_subtype == "html":
            html_body = message.body

        send_kwargs: dict[str, Any] = {
            "subject": message.subject,
            "body": message.body,
            "to": message.to,
            "html_body": html_body,
        }
        attachments = _graph_file_attachments_from_message(message)
        if attachments:
            send_kwargs["attachments"] = attachments
        client.send(**send_kwargs)


class _GraphMailClient:
    def __init__(self) -> None:
        client_id = getattr(settings, "MS_GRAPH_CLIENT_ID", "").strip()
        tenant_id = getattr(settings, "MS_GRAPH_TENANT_ID", "").strip()
        if not client_id or not tenant_id:
            raise GraphConfigurationError(
                "MS_GRAPH_CLIENT_ID and MS_GRAPH_TENANT_ID must be set."
            )

        self._client_id = client_id
        self._tenant_id = tenant_id
        self._cache = msal.SerializableTokenCache()
        self._cache_path = GraphEmailBackend.get_token_cache_path()
        self._load_cache()

        self._app = msal.PublicClientApplication(
            self._client_id,
            authority=f"https://login.microsoftonline.com/{self._tenant_id}",
            token_cache=self._cache,
        )

    def _load_cache(self) -> None:
        if self._cache_path.exists():
            self._cache.deserialize(self._cache_path.read_text(encoding="utf-8"))

    def _persist_cache(self) -> None:
        if not self._cache.has_state_changed:
            return
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(self._cache.serialize(), encoding="utf-8")

    def get_access_token(self) -> str:
        accounts = self._app.get_accounts()
        if not accounts:
            raise GraphAuthError(
                "No cached Graph account. Run `python manage.py graph_auth` to sign in."
            )

        result = self._app.acquire_token_silent(
            GraphEmailBackend.SCOPES,
            account=accounts[0],
        )
        self._persist_cache()

        if not result or "access_token" not in result:
            error = (result or {}).get("error_description") or (result or {}).get("error")
            raise GraphAuthError(
                f"Unable to refresh Graph token: {error or 'unknown error'}. "
                "Run `python manage.py graph_auth` to re-authenticate."
            )

        return result["access_token"]

    def authenticate_interactive(self) -> str:
        result = self._app.acquire_token_interactive(scopes=GraphEmailBackend.SCOPES)
        self._persist_cache()

        if "access_token" not in result:
            error = result.get("error_description") or result.get("error")
            raise GraphAuthError(f"Interactive Graph authentication failed: {error}")

        return result["access_token"]

    def send(
        self,
        *,
        subject: str,
        body: str,
        to: Sequence[str],
        html_body: str | None = None,
        attachments: Sequence[dict[str, Any]] | None = None,
    ) -> None:
        recipients = [email.strip() for email in to if email and email.strip()]
        if not recipients:
            raise GraphSendError("At least one recipient is required.")

        access_token = self.get_access_token()
        content_type = "HTML" if html_body else "Text"
        content = html_body if html_body else body

        payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": content_type,
                    "content": content,
                },
                "toRecipients": [
                    {"emailAddress": {"address": address}} for address in recipients
                ],
            },
            "saveToSentItems": True,
        }
        if attachments:
            payload["message"]["attachments"] = list(attachments)

        response = requests.post(
            f"{GRAPH_API_BASE}/me/sendMail",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )

        if response.status_code >= 400:
            logger.error(
                "Graph sendMail failed (%s): %s",
                response.status_code,
                response.text,
            )
            raise GraphSendError(
                f"Graph sendMail failed ({response.status_code}): {response.text}"
            )


def _graph_file_attachments_from_message(message: EmailMessage) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    mime_root = message.message()

    for part in mime_root.walk():
        if part.get_content_maintype() == "multipart":
            continue

        content_disposition = (part.get("Content-Disposition") or "").lower()
        content_id = part.get("Content-ID")
        if part.get_content_maintype() == "text" and not content_id and "attachment" not in content_disposition:
            continue

        payload = part.get_payload(decode=True)
        if not payload:
            continue

        filename = part.get_filename() or "attachment"
        is_inline = "inline" in content_disposition or bool(content_id)
        graph_att: dict[str, Any] = {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": filename,
            "contentType": part.get_content_type(),
            "contentBytes": base64.b64encode(payload).decode("ascii"),
        }
        if is_inline and content_id:
            graph_att["isInline"] = True
            graph_att["contentId"] = content_id.strip().strip("<>")
        attachments.append(graph_att)

    return attachments


def graph_is_configured() -> bool:
    client_id = getattr(settings, "MS_GRAPH_CLIENT_ID", "").strip()
    tenant_id = getattr(settings, "MS_GRAPH_TENANT_ID", "").strip()
    if not client_id or not tenant_id:
        return False
    return GraphEmailBackend.get_token_cache_path().exists()
