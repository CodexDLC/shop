from allauth.account.decorators import secure_admin_login
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path

from web.shop.views.engine_status_view import EngineStatusView

admin.site.login = secure_admin_login(admin.site.login)
urlpatterns = [path("health/", EngineStatusView.as_view(), name="health"), path("admin/", admin.site.urls)]
urlpatterns += [path("staff/", include("web.staff.urls"))]
urlpatterns += i18n_patterns(
    path("accounts/", include("allauth.urls")),
    *(path("", include(f"web.{feature}.urls")) for feature in (
        "shop", "catalog", "cart", "orders", "payments", "customer", "support"
    )),
    prefix_default_language=False,
)
# Cabinet app installed for reusable primitives; generic library URLs are not exposed yet.
