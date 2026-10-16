from django.urls import path

from web.support.views import SupportPageView

app_name = "support"
urlpatterns = [
    path("service/", SupportPageView.as_view(template_name="support/help.html"), name="help"),
    path("service/mobil/", SupportPageView.as_view(template_name="support/help_mobile.html"), name="help_mobile"),
    path("rechtliches/", SupportPageView.as_view(template_name="support/legal.html"), name="legal"),
    path("rechtliches/mobil/", SupportPageView.as_view(template_name="support/legal_mobile.html"), name="legal_mobile"),
    path("vorschau/emails/", SupportPageView.as_view(template_name="support/emails.html"), name="emails"),
    path("vorschau/404/", SupportPageView.as_view(template_name="support/not_found.html"), name="not_found"),
]
