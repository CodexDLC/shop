from django.http import Http404, HttpResponse
from django.views import View

from web.localization import translate_text
from web.shop.identity import get_store_identity
from web.support.legal_documents import get_legal_document
from web.support.legal_identity import bind_legal_identity, identity_text_lines


class LegalDownloadView(View):
    http_method_names = ["get", "head", "options"]

    def get(self, request, slug):
        try:
            document = bind_legal_identity(get_legal_document(slug))
        except KeyError as exc:
            raise Http404 from exc
        lines = [translate_text(document.title_key), translate_text("legal.status"), document.version,
                 translate_text("legal.draft_notice"), translate_text(document.summary_key)]
        identity = get_store_identity(request)
        for section in document.sections:
            lines.extend(("", translate_text(section.title_key)))
            if section.identity_part:
                lines.extend(identity_text_lines(identity, section.identity_part))
            lines.extend(translate_text(key) for key in section.paragraph_keys)
            for title_key, body_key in section.cards:
                lines.extend((translate_text(title_key), translate_text(body_key)))
            for row in section.rows:
                lines.append(" | ".join(translate_text(key) for key in row))
            lines.extend(translate_text(key) for key in section.form_keys)
        response = HttpResponse("\n\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{document.slug}-{document.version}.txt"'
        response["X-Content-Type-Options"] = "nosniff"
        return response
