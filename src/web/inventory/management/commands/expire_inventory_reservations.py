from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError
from django.utils import timezone

from codex_ecommerce.inventory import InventoryError
from web.inventory.expiry_service import due_reservations, expire_due_reservations


class Command(BaseCommand):
    help = 'Preview due inventory holds; --apply explicitly releases them. Requires a persisted staff actor.'

    def add_arguments(self, parser):
        parser.add_argument('--actor', type=int, required=True)
        parser.add_argument('--batch-size', type=int, default=100)
        parser.add_argument('--apply', action='store_true', dest='apply')

    def handle(self, *args, **options):
        now = timezone.now()
        try:
            actor = get_user_model().objects.filter(pk=options['actor']).first()
            function = expire_due_reservations if options['apply'] else due_reservations
            summary = function(actor=actor, now=now, batch_size=options['batch_size'])
        except (PermissionDenied, InventoryError) as error:
            raise CommandError('Inventory expiry denied or invalid operation.') from error
        except DatabaseError:
            raise CommandError('Inventory expiry database unavailable; check configuration and migrations.') from None
        self.stdout.write(f'at={now.isoformat()} dry_run={not options["apply"]} scanned={summary.scanned} expired={summary.expired} '
            f'skipped={summary.skipped} has_more={summary.has_more}')
