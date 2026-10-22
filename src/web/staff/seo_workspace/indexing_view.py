from django.conf import settings

from web.seo.origin import indexing_enabled, public_origin

from .base_view import SeoWorkspaceView


class SeoIndexingView(SeoWorkspaceView):
    template_name = "staff/seo/indexing.html"
    seo_section = "indexing"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(indexing_enabled=indexing_enabled(), public_origin=public_origin(),
                       force_noindex=getattr(settings, "SEO_FORCE_NOINDEX", False))
        return context
