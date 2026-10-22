from django.urls import path

from web.staff.views.product_photos_view import ProductPhotosView

urlpatterns = [path("catalog/<int:pk>/photos/", ProductPhotosView.as_view(), name="product_photos")]
