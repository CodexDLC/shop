from django.urls import path

from web.payments.views import PaymentPageView

app_name = "payments"
urlpatterns = [
    path("bestellung/zahlung/", PaymentPageView.as_view(template_name="payments/review.html"), name="review"),
    path("bestellung/zahlung/fehler/", PaymentPageView.as_view(template_name="payments/error.html"), name="error"),
]
