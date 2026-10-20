from .configuration import PREFIX


class OAuthPrivacyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith(PREFIX):
            response["Cache-Control"] = "no-store, private"
            response["Referrer-Policy"] = "same-origin"
            response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
            response["Content-Security-Policy"] = "default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response
