from django.utils.deprecation import MiddlewareMixin


class AuthHeadersMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        match = request.resolver_match
        if match and ((match.url_name or "").startswith(("account_", "mfa_"))
                      or "customer" in match.namespaces):
            response["Cache-Control"] = "no-store, private"
            # Preserve same-origin POST Origin/Referer for Django CSRF while
            # suppressing token-bearing referrers to external resources.
            response["Referrer-Policy"] = "same-origin"
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response
