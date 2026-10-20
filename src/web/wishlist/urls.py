from django.urls import path

from .detail_view import WishlistDetailView
from .mutation_view import WishlistMutationView

app_name = "wishlist"
urlpatterns = [
    path("merkliste/", WishlistDetailView.as_view(), name="detail"),
    path("merkliste/hinzufuegen/", WishlistMutationView.as_view(), name="add"),
    path("merkliste/entfernen/", WishlistMutationView.as_view(remove=True), name="remove"),
]
