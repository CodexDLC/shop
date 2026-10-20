import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from web.support.models import ContactTicket

pytestmark = pytest.mark.django_db
DATA = {'name': 'Local Test', 'email': 'test@example.invalid', 'topic': 'sonstiges',
        'message': 'Please help with this local test.', 'website': ''}


def test_contact_persists_only_allowlisted_data_and_uses_prg_without_email(mailoutbox):
    client = Client()
    attacker = get_user_model().objects.create_user(username='other')
    response = client.post(reverse('support:contact'), {
        **DATA, 'user': attacker.pk, 'resolved': 'true', 'created_at': '2000-01-01',
    })
    assert response.status_code == 302
    ticket = ContactTicket.objects.get()
    assert ticket.user is None
    assert ticket.resolved is False
    assert ticket.message == DATA['message']
    assert mailoutbox == []
    first = client.get(response.url).content.decode()
    assert 'id="contact-saved-status"' not in client.get(response.url).content.decode()
    assert 'id="contact-saved-status"' in first
    assert ContactTicket.objects.count() == 1


def test_contact_csrf_authorship_and_no_get_mutations():
    client = Client(enforce_csrf_checks=True)
    assert client.post(reverse('support:contact'), DATA).status_code == 403
    assert client.get(reverse('support:contact')).status_code == 405
    owner = get_user_model().objects.create_user(username='contact-owner')
    authenticated = Client()
    authenticated.force_login(owner)
    authenticated.post(reverse('support:contact'), DATA)
    assert ContactTicket.objects.get().user_id == owner.pk


def test_contact_errors_preserve_input_and_honeypot_rate_limit_bound_attempts():
    client = Client()
    response = client.post(reverse('support:contact'), {
        **DATA, 'email': 'invalid', 'message': '<script>window.bad=1</script>', 'form_source': 'mobile',
    })
    assert response.status_code == 400
    assert 'no-store' in response['Cache-Control']
    html = response.content.decode()
    assert '&lt;script&gt;window.bad=1&lt;/script&gt;' in html
    assert response.context['contact_form']['email'].errors
    assert client.post(reverse('support:contact'), {**DATA, 'website': 'bot'}).status_code == 400
    for _ in range(3):
        assert client.post(reverse('support:contact'), {**DATA, 'message': ''}).status_code == 400
    assert client.post(reverse('support:contact'), DATA).status_code == 429
    assert ContactTicket.objects.count() == 0
    assert len(client.session['contact_attempts']) == 5


def test_contact_rejects_overlong_fields_without_ticket():
    assert Client().post(reverse('support:contact'), {**DATA, 'message': 'x' * 4001}).status_code == 400
    assert ContactTicket.objects.count() == 0


def test_public_help_get_does_not_read_or_create_tickets(django_assert_num_queries):
    with django_assert_num_queries(0):
        assert Client().get(reverse('support:help')).status_code == 200
        assert Client().get(reverse('support:help_mobile')).status_code == 200
    assert ContactTicket.objects.count() == 0


def test_contact_admin_requires_standard_model_permission():
    url = reverse('admin:support_contactticket_changelist')
    assert Client().get(url).status_code == 302
    staff = get_user_model().objects.create_user(username='support-no-permission', is_staff=True)
    client = Client()
    client.force_login(staff)
    assert client.get(url).status_code == 403
