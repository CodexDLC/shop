from django.urls import path

from .views.callback_view import CallbackView
from .views.connect_view import ConnectView
from .views.result_view import ResultView

app_name = "ebay_oauth"
urlpatterns = [
    path("connect/<str:token>/", ConnectView.as_view(), name="connect"),
    path("callback/", CallbackView.as_view(), name="callback"),
    path("result/", ResultView.as_view(), name="result"),
]
