from __future__ import annotations

from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from django_jt.auth.auth901_sync import (
    SyncOutcome,
    SyncPasswordOptions,
    reset_casdoor_token,
    sync_user,
)
from django_jt.auth.base import auth901_organization, auth901_service_credentials


class Command(BaseCommand):
    help = "Sync local users to Auth901 (Casdoor) and backfill auth901_sub."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report actions without calling Auth901 to create users or updating the database.",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Include inactive users (default: only is_active=True with an email).",
        )
        parser.add_argument(
            "--repair",
            action="store_true",
            help="Re-check users that already have auth901_sub; relink or recreate Auth901 rows by email.",
        )
        parser.add_argument(
            "--initial-password",
            default=None,
            help="Initial Casdoor password for new users.",
        )
        parser.add_argument(
            "--require-password-change",
            action="store_true",
            help="Set needUpdatePassword when applying an initial password.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        include_inactive: bool = options["include_inactive"]
        repair: bool = options["repair"]
        initial_password = (options["initial_password"] or "").strip() or None

        password_options = SyncPasswordOptions(
            initial_password=initial_password,
            require_password_change=options["require_password_change"],
        )

        try:
            auth901_service_credentials()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        try:
            auth901_organization(required=True)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        reset_casdoor_token()

        User = get_user_model()
        qs = User.objects.all().order_by("pk")
        if not include_inactive:
            qs = qs.filter(is_active=True)
        qs = qs.exclude(email__isnull=True).exclude(email="")
        if not repair and hasattr(User, "auth901_sub"):
            qs = qs.filter(Q(auth901_sub__isnull=True) | Q(auth901_sub=""))

        counts: Counter[str] = Counter()
        for user in qs:
            try:
                outcome = sync_user(
                    user,
                    dry_run=dry_run,
                    repair=repair,
                    password_options=password_options,
                )
            except Exception as exc:
                outcome = SyncOutcome.ERROR
                self.stderr.write(
                    self.style.ERROR(f"{user.email}: unexpected error: {exc}")
                )
            counts[outcome.value] += 1
            self.stdout.write(f"{user.email}: {outcome.value}")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Summary"))
        for key in SyncOutcome:
            count = counts.get(key.value, 0)
            if count:
                self.stdout.write(f"  {key.value}: {count}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("Dry run — no auth901_sub updates were saved.")
            )
