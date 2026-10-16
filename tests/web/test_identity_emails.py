import pytest
from allauth.account.adapter import get_adapter
from allauth.core.context import request_context
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory


@pytest.mark.parametrize(('prefix', 'key'), [
    ('email_confirmation', 'activate_url'),
    ('email_confirmation_signup', 'activate_url'),
    ('password_reset_key', 'password_reset_url'),
])
def test_account_email_has_html_text_and_embedded_logo(prefix, key):
    request = RequestFactory().get('/', HTTP_HOST='localhost')
    request.user = AnonymousUser()
    url = 'https://example.test/accounts/confirm/example-token/?a=1&b=2'
    with request_context(request):
        message = get_adapter().render_mail('account/email/' + prefix, 'customer@example.test', {key: url})
    assert message.subject.startswith('[Männermasche] ')
    assert url in message.body
    assert len(message.alternatives) == 1
    html = message.alternatives[0].content
    assert 'a=1&amp;b=2' in html
    assert 'cid:maennermasche-logo' in html
    assert '<script' not in html and 'fonts.googleapis' not in html
    assert '[email.' not in html
    assert message.attachments[0]['Content-ID'] == '<maennermasche-logo>'
    assert message.attachments[0].get_payload(decode=True).startswith(b'\x89PNG')
    assert 'multipart/alternative' in message.message().as_string()
