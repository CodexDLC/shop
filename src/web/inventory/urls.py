from django.urls import path

from .endpoint import expire_due

app_name = 'inventory_internal'
urlpatterns = [path('expiry/', expire_due, name='expire_due')]
