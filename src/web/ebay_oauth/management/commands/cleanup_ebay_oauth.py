from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from ...models import AuthorizationFlow, Invitation


class Command(BaseCommand):
    help = "Delete expired operational invitations and authorization attempts; never delete seller credentials."

    def handle(self, *args, **options):
        with transaction.atomic():
            AuthorizationFlow.objects.filter(expires_at__lte=timezone.now()).delete()
            Invitation.objects.filter(expires_at__lte=timezone.now()).delete()
        self.stdout.write("Expired OAuth invitations and attempts removed. Seller connections preserved.")
