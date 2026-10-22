from django.utils.deprecation import MiddlewareMixin

from .metadata import page_metadata
from .policy import PagePolicy


class SeoMiddleware(MiddlewareMixin):
    def process_template_response(self, request, response):
        response.context_data['seo'] = page_metadata(request, response.context_data, status=response.status_code)
        return response

    def process_response(self, request, response):
        context = getattr(response, 'context_data', None) or {}
        policy = PagePolicy(request, context, status=response.status_code)
        existing = [part.strip() for part in response.get('X-Robots-Tag', '').split(',') if part.strip()]
        # JSON endpoints already carry an explicit noindex contract. Keep that
        # wire representation; HTML and unprotected responses receive the policy.
        if (response.get('Content-Type', '').split(';')[0] != 'text/html'
                and any(part.lower() in {'noindex', 'none'} for part in existing)):
            return response
        directives = existing + policy.robots.split(', ')
        if 'noindex' in directives or 'none' in directives:
            directives = [part for part in directives if part != 'index']
        if 'nofollow' in directives or 'none' in directives:
            directives = [part for part in directives if part != 'follow']
        response['X-Robots-Tag'] = ', '.join(dict.fromkeys(directives))
        return response
