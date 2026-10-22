from allauth.account.decorators import secure_admin_login
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from web.seo.views import robots, sitemap
from web.shop.views.engine_status_view import EngineStatusView

admin.site.login = secure_admin_login(admin.site.login)
handler404 = "web.support.not_found.not_found"
urlpatterns = [path("health/", EngineStatusView.as_view(), name="health"), path("admin/", admin.site.urls)]
urlpatterns += [path("robots.txt", robots, name="robots"), path("sitemap.xml", sitemap, name="sitemap")]
urlpatterns += [path("integrations/ebay/", include("web.ebay_notifications.urls"))]
urlpatterns += [path("integrations/ebay/oauth/", include("web.ebay_oauth.urls"))]
urlpatterns += i18n_patterns(
    path("i18n/", include("django.conf.urls.i18n")),
    path("staff/", include("web.staff.urls")),
    path("accounts/", include("allauth.urls")),
    *(path("", include(f"web.{feature}.urls")) for feature in (
        "shop", "catalog", "cart", "orders", "payments", "customer", "support", "wishlist"
    )),
    prefix_default_language=False,
)
# Cabinet app installed for reusable primitives; generic library URLs are not exposed yet.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
