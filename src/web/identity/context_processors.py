from django.urls import reverse

from web.storefront.pages import page_manifest


def auth_context(request):
    match = request.resolver_match
    if not match or not ((match.url_name or "").startswith(("account_", "mfa_"))
                         or match.view_name == "customer:overview"):
        return {}
    return {"demo_mode": False, "shop_texts": {}, "shop_routes": {
        page["source"]: reverse(f"{page['feature']}:{page['name']}") for page in page_manifest()
    }}
