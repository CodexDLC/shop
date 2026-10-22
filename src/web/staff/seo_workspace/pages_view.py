from web.seo.workspace import search_pages

from .base_view import SeoWorkspaceView


class SeoPagesView(SeoWorkspaceView):
    template_name = "staff/seo/pages.html"
    seo_section = "pages"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "")[:200]
        kind = self.request.GET.get("kind", "")
        if kind not in ("product", "category", "brand", "static"):
            kind = ""
        context.update(search_query=query, selected_kind=kind,
                       page_obj=search_pages(query=query, kind=kind, language=self.content_language(),
                                             page=self.request.GET.get("page", 1)))
        return context
