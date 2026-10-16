from django.apps import AppConfig


class IdentityConfig(AppConfig):
    name = "web.identity"

    def ready(self):
        from . import checks  # noqa: F401
