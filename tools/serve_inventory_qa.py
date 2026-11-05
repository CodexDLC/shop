"""Serve disposable, loopback-only inventory fixtures for manual browser QA.

Never loads .env or connects to the working database. Stop with Ctrl-C; the
temporary SQLite database and its fake accounts are removed on normal exit.
"""
import argparse
import os
import socket
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8047)
    args = parser.parse_args()
    if not 8040 <= args.port <= 8099:
        parser.error('Use a dedicated QA port between 8040 and 8099.')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', args.port))

    # Explicit test settings, never manage_local or an inherited settings module.
    os.environ['DJANGO_SETTINGS_MODULE'] = 'web.config.settings.test'
    os.environ['DJANGO_SECRET_KEY'] = 'inventory-browser-qa-not-a-live-secret'
    sys.path.insert(0, str(ROOT / 'src'))
    from django.conf import settings

    runtime_root = ROOT / 'tmp' / 'inventory-qa'
    runtime_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='run-', dir=runtime_root) as directory:
        database = Path(directory).resolve() / 'qa.sqlite3'
        if not database.is_relative_to(runtime_root.resolve()):
            raise RuntimeError('Refusing database outside the QA runtime directory.')
        settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(database)}}
        settings.ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
        # Cookies are host-scoped, not port-scoped: keep this throwaway server
        # separate from the user's ordinary local shop session on port 8030.
        settings.SESSION_COOKIE_NAME = 'inventory_qa_sessionid'
        settings.CSRF_COOKIE_NAME = 'inventory_qa_csrftoken'
        settings.LANGUAGE_COOKIE_NAME = 'inventory_qa_language'
        settings.DEBUG = True
        settings.SHOP_CHECKOUT_STOCK_MODE = 'inventory_test'
        settings.INVENTORY_EXPIRY_ENABLED = False
        settings.SHOP_STAFF_MFA_REQUIRED = False
        settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

        import django

        django.setup()
        from allauth.account.models import EmailAddress
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        from django.core.management import call_command
        from django.db import connections
        from django.utils import timezone

        from codex_ecommerce.inventory import OperationContext
        from web.catalog.models import Product, ProductVariant
        from web.inventory import services

        call_command('migrate', verbosity=0, interactive=False)
        call_command('seed_demo_catalog', verbosity=0)
        users = get_user_model()
        owner = users.objects.create_superuser('inventory-owner', 'inventory-owner@example.test', 'inventory-qa-only')
        reader = users.objects.create_user('inventory-reader', 'inventory-reader@example.test', 'inventory-qa-only', is_staff=True)
        reader.user_permissions.set(Permission.objects.filter(content_type__app_label='inventory', codename__in=[
            'view_stockbalance', 'view_inventorymovement', 'view_reservationline',
        ]))
        for user in (owner, reader):
            EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        variants = list(ProductVariant.objects.order_by('pk')[:5])
        for index, quantity in ((1, 0), (2, 8), (3, 3), (4, 2)):
            variant = variants[index]
            services.initialize(actor=owner, variant_id=variant.pk, quantity=quantity,
                context=OperationContext(f'qa-init-{index}', 'staff', str(owner.pk), 'Browser QA fixture', 0))
        now = timezone.now()
        services.reserve(actor=owner, variant_id=variants[3].pk, reservation_id='qa-active-reserve', quantity=2,
            expires_at=now + timedelta(hours=1), now=now,
            context=OperationContext('qa-reserve', 'staff', str(owner.pk), 'Browser QA fixture', 1))
        old = now - timedelta(hours=1)
        services.reserve(actor=owner, variant_id=variants[2].pk, reservation_id='qa-expired-reserve', quantity=1,
            expires_at=old + timedelta(minutes=30), now=old,
            context=OperationContext('qa-expired', 'staff', str(owner.pk), 'Browser QA fixture', 1))
        returned_variant = variants[4]
        services.reserve(actor=owner, variant_id=returned_variant.pk, reservation_id='qa-checked-return', quantity=1,
            expires_at=now + timedelta(hours=1), now=now,
            context=OperationContext('qa-return-hold', 'staff', str(owner.pk), 'Browser QA fixture', 1))
        services.commit(actor=owner, variant_id=returned_variant.pk, reservation_id='qa-checked-return',
            expected_reservation_revision=1, now=now,
            context=OperationContext('qa-return-commit', 'staff', str(owner.pk), 'Browser QA fixture', 2))
        services.fulfill(actor=owner, variant_id=returned_variant.pk, reservation_id='qa-checked-return', quantity=1,
            expected_reservation_revision=2, now=now,
            context=OperationContext('qa-return-fulfill', 'staff', str(owner.pk), 'Browser QA fixture', 3))
        services.checked_return(actor=owner, variant_id=returned_variant.pk, reservation_id='qa-checked-return', quantity=1,
            expected_reservation_revision=3, now=now, received=True, inspected=True,
            context=OperationContext('qa-return-accept', 'staff', str(owner.pk), 'Browser QA fixture', 4))
        # Make the feature's fake SKU names recognizable on narrow screens.
        Product.objects.filter(pk=variants[0].product_id).update(model_name='QA склад / Lager — размеры и цвета')
        print(f'QA runtime: {directory}', flush=True)
        print(f'QA URL: http://127.0.0.1:{args.port}/ru/staff/stock/', flush=True)
        print('Fake users: inventory-owner / inventory-reader; password: inventory-qa-only', flush=True)
        print('Only disposable SQLite fixtures; no working stock, .env or external APIs.', flush=True)
        try:
            call_command('runserver', f'127.0.0.1:{args.port}', use_reloader=False)
        finally:
            connections.close_all()


if __name__ == '__main__':
    main()
