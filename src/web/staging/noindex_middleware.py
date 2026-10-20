from django.utils.deprecation import MiddlewareMixin


class NoIndexMiddleware(MiddlewareMixin):
    """Staging-only crawler directive, including redirects and error responses."""

    def process_response(self, request, response):
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response
