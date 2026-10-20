import pytest
from django.conf import Settings
from django.http import HttpResponse, HttpResponseRedirect
from django.test import RequestFactory

from web.staging.noindex_middleware import NoIndexMiddleware


@pytest.mark.parametrize("response", [HttpResponse("ok"), HttpResponseRedirect("/accounts/login/"),
                                     HttpResponse(status=404), HttpResponse(status=500)])
def test_staging_noindex_includes_errors_and_redirects(response):
    request = RequestFactory().get("/")
    assert NoIndexMiddleware(lambda request: response)(request)["X-Robots-Tag"] == "noindex, nofollow, noarchive"


def test_staging_uses_https_host_only_cookies_and_captured_mail():
    settings = Settings("web.config.settings.staging")
    assert not settings.DEBUG
    assert settings.ALLOWED_HOSTS == ["shop.pinlite.dev"]
    assert settings.SECURE_SSL_REDIRECT and settings.SESSION_COOKIE_SECURE and settings.CSRF_COOKIE_SECURE
    assert settings.SESSION_COOKIE_DOMAIN is None and settings.CSRF_COOKIE_DOMAIN is None
    assert settings.SESSION_COOKIE_NAME != "sessionid"
    assert settings.MAILERS["default"]["OPTIONS"]["host"] == "mailpit"
    assert not settings.SECURE_HSTS_INCLUDE_SUBDOMAINS
