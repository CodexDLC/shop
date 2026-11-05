from django.db import models

from web.inventory.write_access import require_service_write


class BalanceQuerySet(models.QuerySet):
    def update(self, **kwargs):
        require_service_write()
        return super().update(**kwargs)

    def delete(self):
        require_service_write()
        return super().delete()

    def bulk_create(self, *args, **kwargs):
        require_service_write()
        return super().bulk_create(*args, **kwargs)

    def bulk_update(self, *args, **kwargs):
        require_service_write()
        return super().bulk_update(*args, **kwargs)
