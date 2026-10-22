import pytest

from web.orders.address_form import CheckoutAddressForm

HOME = {'email': 'checkout@example.test', 'first_name': 'Max', 'last_name': 'Muster',
        'street': 'Musterstraße 12', 'postal_code': '10115', 'city': 'Berlin', 'country': 'DE'}
BILLING = {'billing_separate': True, 'billing_first_name': 'Erika', 'billing_last_name': 'Beispiel',
           'billing_street': 'Beispielweg 7', 'billing_postal_code': '10117',
           'billing_city': 'Berlin', 'billing_country': 'DE'}


def test_home_checkout_keeps_legacy_input_and_normalizes_unused_fields():
    form = CheckoutAddressForm(HOME | {'post_number': 'unused', 'billing_first_name': 'Unused'})
    assert form.is_valid(), form.errors
    assert form.cleaned_data['shipping_type'] == 'home'
    assert form.cleaned_data['billing_separate'] is False
    assert form.cleaned_data['post_number'] == ''
    assert form.cleaned_data['billing_first_name'] == ''


def test_packstation_requires_separate_billing_and_postnummer():
    form = CheckoutAddressForm(HOME | {'shipping_type': 'packstation', 'street': '',
                                     'post_number': '12345678', 'packstation_number': '123'})
    assert not form.is_valid()
    assert 'billing_separate' in form.errors
    valid = CheckoutAddressForm(HOME | BILLING | {'shipping_type': 'packstation', 'street': '',
                                                'post_number': '12345678', 'packstation_number': '123'})
    assert valid.is_valid(), valid.errors
    assert valid.cleaned_data['street'] == 'Packstation 123'


@pytest.mark.parametrize('changed', [
    {'post_number': ''}, {'post_number': '1234abc'}, {'post_number': '١٢٣٤٥٦٧٨'},
    {'packstation_number': ''}, {'packstation_number': '12a'}, {'postal_code': '1234'},
    {'billing_street': 'Packstation 123'}, {'billing_country': 'AT'}, {'billing_city': ''},
])
def test_packstation_and_billing_reject_invalid_active_fields(changed):
    form = CheckoutAddressForm(HOME | BILLING | {'shipping_type': 'packstation', 'street': '',
                                              'post_number': '12345678', 'packstation_number': '123'} | changed)
    assert not form.is_valid()


def test_home_must_not_smuggle_packstation_into_street():
    form = CheckoutAddressForm(HOME | {'street': 'Packstation 123'})
    assert not form.is_valid()
