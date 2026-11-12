"""Bootstrap Gmail OAuth token for API sending."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from google_auth_oauthlib.flow import InstalledAppFlow

from django_jt.backends.email.gmail import GmailBackend


class Command(BaseCommand):
    help = (
        "Run a one-time browser OAuth flow and save Gmail credentials to "
        f"{GmailBackend.TOKEN_PATH}."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-browser",
            action="store_true",
            help="Print the Google sign-in URL instead of opening a browser.",
        )

    def handle(self, *args, **options):
        client_secret_path = GmailBackend.get_client_secret_path()
        if not client_secret_path.is_file():
            raise CommandError(
                f"Gmail OAuth client secret not found at {client_secret_path}. "
                "Download the Desktop OAuth JSON from Google Cloud and save it there."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_path),
            GmailBackend.SCOPES,
        )
        open_browser = not options["no_browser"]

        try:
            creds = flow.run_local_server(port=0, open_browser=open_browser)
            token_path = GmailBackend.save_credentials(creds)
        except Exception as exc:
            raise CommandError(f"Gmail OAuth failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"Gmail OAuth token saved to {token_path}."))
        self.stdout.write(
            "Set EMAIL_BACKEND=django_jt.backends.email.gmail.GmailBackend and "
            "DEFAULT_FROM_EMAIL to the Gmail address that signed in."
        )
