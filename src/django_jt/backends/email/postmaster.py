import os

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.mail.backends.base import BaseEmailBackend

DEFAULT_POSTMASTER_URI = "https://postmaster.new901.io"


def _setting(name, default=None):
    return getattr(settings, name, None) or os.getenv(name, default)


class PostMasterEmailBackend(BaseEmailBackend):
    user_sub: str | int | None = None
    cache_key = "postmaster:access_token"

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.postmaster_uri = _setting("POSTMASTER_URI", DEFAULT_POSTMASTER_URI)
        self.client_id = _setting("POSTMASTER_CLIENT_ID")
        self.client_secret = _setting("POSTMASTER_CLIENT_SECRET")
        self.auth_endpoint = self.postmaster_uri + "/api/v1/token/"
        self.send_endpoint = self.postmaster_uri + "/api/v1/emails/"

    def _authorize(self) -> str:
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "POSTMASTER_CLIENT_ID and POSTMASTER_CLIENT_SECRET must be set"
            )
        res = requests.post(
            self.auth_endpoint,
            json={"client_id": self.client_id, "client_secret": self.client_secret},
            timeout=15,
        )
        res.raise_for_status()
        data = res.json()
        token = data["access_token"]
        cache.set(
            self.cache_key, token, timeout=max(int(data.get("expires_in", 0)) - 60, 0)
        )
        return token

    def _token(self) -> str:
        return cache.get(self.cache_key) or self._authorize()

    def _post(self, payload: dict) -> requests.Response:
        return requests.post(
            self.send_endpoint,
            headers={"Authorization": f"Bearer {self._token()}"},
            json=payload,
            timeout=15,
        )

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            payload = {
                "to": message.to,
                "cc": message.cc,
                "bcc": message.bcc,
                "subject": message.subject,
                "text": message.body,
            }
            if message.reply_to:
                payload["reply_to"] = message.reply_to[0]
            for content, mimetype in getattr(message, "alternatives", []):
                if mimetype == "text/html":
                    payload["html"] = content
            if self.user_sub:
                payload["user_sub"] = str(self.user_sub)
            try:
                res = self._post(payload)
                if res.status_code == 401:
                    cache.delete(self.cache_key)
                    res = self._post(payload)
                res.raise_for_status()
                sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
        return sent
