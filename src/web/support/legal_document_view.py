from django.http import Http404
from django.urls import reverse

from web.support.legal_documents import get_legal_document, legal_documents
from web.support.legal_identity import bind_legal_identity
from web.support.views import SupportPageView


class LegalDocumentView(SupportPageView):
    template_name = "support/legal.html"
    document_slug = "datenschutz"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            document = get_legal_document(self.kwargs.get("slug", self.document_slug))
        except KeyError as exc:
            raise Http404 from exc
        context.update(
            legal_document=bind_legal_identity(document),
            legal_documents=legal_documents(),
            related_documents=tuple(item for item in legal_documents() if item.slug != document.slug),
            legal_download_url=reverse("support:legal_download", kwargs={"slug": document.slug}),
        )
        return context
