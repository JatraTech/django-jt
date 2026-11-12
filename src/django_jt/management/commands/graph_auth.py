"""Interactive Microsoft Graph authentication for delegated mail sending."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from django_jt.backends.email.graph import (
    GraphAuthError,
    GraphConfigurationError,
    GraphEmailBackend,
)


class Command(BaseCommand):
    help = (
        "Sign in to Microsoft Graph interactively and refresh the delegated token cache. "
        "Run this when silent token refresh fails."
    )

    def handle(self, *args, **options):
        try:
            GraphEmailBackend.authenticate_interactive()
        except GraphConfigurationError as exc:
            raise CommandError(str(exc)) from exc
        except GraphAuthError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Graph authentication succeeded. Token cache updated."
            )
        )
