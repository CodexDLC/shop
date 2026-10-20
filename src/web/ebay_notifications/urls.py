from django.urls import path

from .views import AccountDeletionView

app_name = "ebay_notifications"
urlpatterns = [path("account-deletion/", AccountDeletionView.as_view(), name="account_deletion")]
