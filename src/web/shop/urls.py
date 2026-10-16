from django.urls import path

from web.shop.views.home_view import HomeView

app_name = "shop"
urlpatterns = [
    path("", HomeView.as_view(template_name="shop/home.html"), name="home"),
]
