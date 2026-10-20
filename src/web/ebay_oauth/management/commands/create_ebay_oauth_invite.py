import os
import re
import secrets
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from ...configuration import PREFIX, configuration
from ...flow_service import digest
from ...models import Invitation
from ...rejected import OAuthRejected


class Command(BaseCommand):
    help = "Create a 24-hour seller OAuth invitation; write capability URL only to a new private file."

    def add_arguments(self, parser):
        parser.add_argument("--seller", required=True)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        seller = options["seller"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", seller):
            raise CommandError("Invalid seller name.")
        try:
            base, _, _ = configuration()
        except OAuthRejected:
            raise CommandError("Seller OAuth configuration is incomplete.") from None
        token = secrets.token_hex(32)
        output = Path(options["output"])
        fd = None
        try:
            # Refuse overwrite/symlink; never send capability URL to stdout or logs.
            fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with transaction.atomic():
                Invitation.objects.create(token_hash=digest(token), expected_seller=seller.casefold(),
                                          expires_at=timezone.now() + timedelta(hours=24))
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    fd = None
                    stream.write(base + PREFIX + "connect/" + token + "/\n")
            self.stdout.write("Private invitation file created. Valid for 24 hours and one successful connection.")
        except OSError:
            raise CommandError("Unable to create private invitation file; nothing overwritten.") from None
        finally:
            if fd is not None:
                os.close(fd)
