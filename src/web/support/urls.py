from django.urls import path

from web.support.contact_create_view import ContactCreateView
from web.support.legal_document_view import LegalDocumentView
from web.support.legal_download_view import LegalDownloadView
from web.support.views import SupportPageView

app_name = "support"
urlpatterns = [
    path("service/kontakt/", ContactCreateView.as_view(), name="contact"),
    path("service/", SupportPageView.as_view(template_name="support/help.html"), name="help"),
    path("service/mobil/", SupportPageView.as_view(template_name="support/help_mobile.html"), name="help_mobile"),
    path("rechtliches/", LegalDocumentView.as_view(), name="legal"),
    path("rechtliches/mobil/", LegalDocumentView.as_view(), name="legal_mobile"),
    path("rechtliches/impressum/", LegalDocumentView.as_view(document_slug="impressum"), name="impressum"),
    path("rechtliches/datenschutz/", LegalDocumentView.as_view(), name="datenschutz"),
    path("rechtliches/agb/", LegalDocumentView.as_view(document_slug="agb"), name="agb"),
    path("rechtliches/widerruf/", LegalDocumentView.as_view(document_slug="widerruf"), name="widerruf"),
    path("rechtliches/versand-zahlung/", LegalDocumentView.as_view(document_slug="versand-zahlung"),
         name="versand_zahlung"),
    path("rechtliches/<slug:slug>/download/", LegalDownloadView.as_view(), name="legal_download"),
    path("vorschau/emails/", SupportPageView.as_view(template_name="support/emails.html"), name="emails"),
    path("vorschau/404/", SupportPageView.as_view(template_name="support/not_found.html"), name="not_found"),
]
