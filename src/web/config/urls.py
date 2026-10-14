from django.contrib import admin
from django.urls import path

from web.shop.views.engine_status_view import EngineStatusView
from web.shop.views.home_view import HomeView

urlpatterns = [path("", HomeView.as_view(), name="home"), path("health/", EngineStatusView.as_view(), name="health"), path("admin/", admin.site.urls)]
# Cabinet app installed for reusable primitives; generic library URLs are not exposed yet.
